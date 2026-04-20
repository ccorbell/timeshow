#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import random
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

_DATA_DIR = Path(__file__).parent.parent / "_data"
_CACHE_DB = _DATA_DIR / "image_cache.db"
_CACHE_MAX_AGE_HOURS = 24


class ImageCollector:
    """
    ImageCollector is a class which can show a sequence
    of image files, either in order or random order,
    displaying each for a given duration with controls
    to pause and continue, and with a timer readout
    showing how much time is remaining for each image.

    The primary use case for this class is for artist
    training, drawing from timed reference images, such
    as figure gesture drawing from reference.

    The image files to be shown can be found in
    a single directory, from a search of a directory
    tree, or from an index file that lists the
    url of each image (with file:/// urls supported
    for local files).
    """
    SETTINGS_MODE_SHALLOW_DIR = "shallow_dir"
    SETTINGS_MODE_DEEP_DIR = "deep_dir"
    SETTINGS_MODE_URL_INDEX = "url_index"

    DEFAULT_IMAGE_TYPES = ["png", "jpg", "webp", "gif", "tiff"]

    def __init__(self,
                 mode,
                 path,
                 include_image_types: list = None):
        self.mode = mode
        self.path = path
        self.image_urls = []
        self.image_types = list(ImageCollector.DEFAULT_IMAGE_TYPES)
        if include_image_types is not None:
            self.image_types = include_image_types

        self.selected_images = []

    # ------------------------------------------------------------------
    # Cache helpers (used only for SETTINGS_MODE_DEEP_DIR)
    # ------------------------------------------------------------------

    def _valid_exts(self):
        exts = set()
        for ext in self.image_types:
            ext = ext.lower().lstrip(".")
            if ext == "jpg":
                exts.update(["jpg", "jpeg"])
            elif ext == "tif":
                exts.update(["tif", "tiff"])
            else:
                exts.add(ext)
        return exts

    @staticmethod
    def _open_cache_db():
        _DATA_DIR.mkdir(exist_ok=True)
        db = sqlite3.connect(str(_CACHE_DB), check_same_thread=False)
        db.execute("""
            CREATE TABLE IF NOT EXISTS cache_meta (
                root TEXT PRIMARY KEY,
                last_rebuilt REAL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS images (
                root TEXT NOT NULL,
                path TEXT NOT NULL,
                UNIQUE(root, path)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_images_root ON images(root)")
        db.commit()
        return db

    @staticmethod
    def _cache_age_hours(db, root):
        row = db.execute(
            "SELECT last_rebuilt FROM cache_meta WHERE root=?", (root,)
        ).fetchone()
        if row is None:
            return float("inf")
        return (time.time() - row[0]) / 3600.0

    @staticmethod
    def _sample_from_cache(db, root, max_images):
        if max_images > 0:
            rows = db.execute(
                "SELECT path FROM images WHERE root=? ORDER BY RANDOM() LIMIT ?",
                (root, max_images)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT path FROM images WHERE root=? ORDER BY RANDOM()",
                (root,)
            ).fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def _walk_and_collect(root, valid_exts):
        """Walk root and return list of file:// URIs for all matching images."""
        results = []
        for dirpath, _, files in os.walk(root):
            for name in files:
                if os.path.splitext(name)[1][1:].lower() in valid_exts:
                    full = os.path.join(dirpath, name)
                    results.append(Path(full).resolve().as_uri())
        return results

    @staticmethod
    def _rebuild_cache(db, root, valid_exts):
        paths = ImageCollector._walk_and_collect(root, valid_exts)
        db.execute("DELETE FROM images WHERE root=?", (root,))
        db.executemany(
            "INSERT OR IGNORE INTO images(root, path) VALUES(?, ?)",
            ((root, p) for p in paths)
        )
        db.execute(
            "INSERT OR REPLACE INTO cache_meta(root, last_rebuilt) VALUES(?, ?)",
            (root, time.time())
        )
        db.commit()
        return paths

    def _rebuild_cache_background(self, root, valid_exts):
        def _worker():
            try:
                db = self._open_cache_db()
                self._rebuild_cache(db, root, valid_exts)
                db.close()
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def locate_images(self):
        self.image_urls = []

        valid_exts = self._valid_exts()

        def is_supported_image(path):
            return os.path.splitext(path)[1][1:].lower() in valid_exts

        def to_file_uri(path):
            return Path(os.fsdecode(path)).resolve().as_uri()

        if self.mode == ImageCollector.SETTINGS_MODE_SHALLOW_DIR:
            if not os.path.isdir(self.path):
                return
            for entry in os.listdir(self.path):
                full_path = os.path.join(self.path, entry)
                if os.path.isfile(full_path) and is_supported_image(full_path):
                    self.image_urls.append(to_file_uri(full_path))

        elif self.mode == ImageCollector.SETTINGS_MODE_DEEP_DIR:
            if not os.path.isdir(self.path):
                return
            root = str(Path(self.path).resolve())
            try:
                db = self._open_cache_db()
                age = self._cache_age_hours(db, root)
                if age < _CACHE_MAX_AGE_HOURS:
                    # Cache is fresh — load all paths for select_images to sample.
                    rows = db.execute(
                        "SELECT path FROM images WHERE root=?", (root,)
                    ).fetchall()
                    self.image_urls = [r[0] for r in rows]
                    db.close()
                    return

                has_stale = age < float("inf")
                if has_stale:
                    # Use stale cache immediately and rebuild in background.
                    rows = db.execute(
                        "SELECT path FROM images WHERE root=?", (root,)
                    ).fetchall()
                    self.image_urls = [r[0] for r in rows]
                    db.close()
                    self._rebuild_cache_background(root, valid_exts)
                    return

                # Cold cache — full walk, populate cache, return results.
                paths = self._rebuild_cache(db, root, valid_exts)
                db.close()
                self.image_urls = paths

            except Exception:
                # Fall back to plain walk if anything goes wrong with the cache.
                self.image_urls = self._walk_and_collect(root, valid_exts)

        elif self.mode == ImageCollector.SETTINGS_MODE_URL_INDEX:
            if not os.path.isfile(self.path):
                return

            index_dir = os.path.dirname(os.path.abspath(self.path))
            with open(self.path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parsed = urlparse(line)
                    if parsed.scheme:
                        self.image_urls.append(line)
                        continue

                    candidate = line if os.path.isabs(line) else os.path.join(index_dir, line)
                    if os.path.isfile(candidate):
                        self.image_urls.append(to_file_uri(candidate))

    def select_images(self,
                      random_order=True,
                      max_images=0):
        # For deep_dir with a warm cache and a max_images limit we can do the
        # random sampling directly in SQLite rather than loading all URIs first.
        if (self.mode == ImageCollector.SETTINGS_MODE_DEEP_DIR
                and max_images > 0
                and len(self.image_urls) > max_images):
            root = str(Path(self.path).resolve())
            try:
                db = self._open_cache_db()
                if self._cache_age_hours(db, root) < _CACHE_MAX_AGE_HOURS:
                    self.selected_images = self._sample_from_cache(db, root, max_images)
                    db.close()
                    return self.selected_images
                db.close()
            except Exception:
                pass

        self.selected_images = self.image_urls.copy()
        if random_order:
            random.shuffle(self.selected_images)
        if max_images > 0:
            self.selected_images = self.selected_images[:max_images]

        return self.selected_images
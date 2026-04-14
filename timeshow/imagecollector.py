#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from urllib.parse import urlparse

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
                 include_image_types:list = None):
        self.mode = mode
        self.path = path
        self.image_urls = []
        self.image_types = list(ImageCollector.DEFAULT_IMAGE_TYPES)
        if include_image_types is not None:
            self.image_types = include_image_types

        self.selected_images = []

    def locate_images(self):
        # clear any existing images
        self.image_urls = []

        valid_exts = set()
        for ext in self.image_types:
            ext = ext.lower().lstrip(".")
            if ext == "jpg":
                valid_exts.update(["jpg", "jpeg"])
            elif ext == "tif":
                valid_exts.update(["tif", "tiff"])
            else:
                valid_exts.add(ext)

        def is_supported_image(path):
            ext = os.path.splitext(path)[1][1:].lower()
            return ext in valid_exts

        def to_file_uri(path):
            return Path(os.fsdecode(path)).resolve().as_uri()

        # load images according to mode
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
            for root, _, files in os.walk(self.path):
                for name in files:
                    full_path = os.path.join(root, name)
                    if is_supported_image(full_path):
                        self.image_urls.append(to_file_uri(full_path))
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

                    # Treat plain paths as files relative to the index location.
                    candidate = line if os.path.isabs(line) else os.path.join(index_dir, line)
                    if os.path.isfile(candidate):
                        self.image_urls.append(to_file_uri(candidate))

    def select_images(self,
                 random_order=True,
                 max_images=0):
        import random

        # select the images to show
        # if random_order is selected they should be shuffled
        # if max_images is positive, only the first max_images should
        # be selected (after shuffling)

        # make selected_images a copy of self.image_urls
        self.selected_images = self.image_urls.copy()
        if random_order:
            random.shuffle(self.selected_images)
        if max_images > 0:
            self.selected_images = self.selected_images[:max_images]

        return self.selected_images



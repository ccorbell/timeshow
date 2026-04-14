#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import mimetypes
import os
from base64 import b64encode
from urllib.parse import unquote, urlparse

import webview


DEFAULT_SECONDS_PER_IMAGE = 60


def _file_uri_to_path(image_url):
    parsed = urlparse(image_url)
    if parsed.scheme != "file":
        return None

    path = unquote(parsed.path or "")

    # Support file://localhost/... and UNC-like hosts when present.
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"

    # file:///C:/... on Windows contains a leading slash before drive letter.
    if os.name == "nt" and len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]

    return path


class SlideshowApi:
    def __init__(self):
        self._resolved_src_cache = {}

    def resolve_image(self, image_url):
        if image_url in self._resolved_src_cache:
            return self._resolved_src_cache[image_url]

        parsed = urlparse(image_url)
        if parsed.scheme != "file":
            self._resolved_src_cache[image_url] = image_url
            return image_url

        image_path = _file_uri_to_path(image_url)
        if not image_path or not os.path.isfile(image_path):
            return ""

        with open(image_path, "rb") as image_file:
            encoded = b64encode(image_file.read()).decode("ascii")

        mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
        resolved_src = f"data:{mime_type};base64,{encoded}"
        self._resolved_src_cache[image_url] = resolved_src
        return resolved_src


def run_slideshow_window(image_urls, time_s=None):
    if not image_urls:
        return

    try:
        seconds_per_image = int(time_s)
    except (TypeError, ValueError):
        seconds_per_image = DEFAULT_SECONDS_PER_IMAGE

    if seconds_per_image <= 0:
        seconds_per_image = DEFAULT_SECONDS_PER_IMAGE

    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>timeshow</title>
  <style>
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      background: #111;
      color: #f0f0f0;
      font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;
    }

    .app {
      display: grid;
      grid-template-rows: 1fr auto;
      width: 100%;
      height: 100%;
    }

    .stage {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 0;
      padding: 10px;
    }

    .stage img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      user-select: none;
      -webkit-user-drag: none;
    }

    .controls {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-top: 1px solid #333;
      background: #1b1b1b;
      flex-wrap: wrap;
    }

    .meta {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 14px;
    }

    .timer {
      font-variant-numeric: tabular-nums;
      min-width: 70px;
    }

    .buttons {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    button {
      border: 1px solid #555;
      background: #2b2b2b;
      color: #fff;
      border-radius: 6px;
      padding: 6px 12px;
      cursor: pointer;
      font-size: 14px;
    }

    button:hover {
      background: #3a3a3a;
    }
  </style>
</head>
<body>
  <div class=\"app\">
    <div class=\"stage\">
      <img id=\"slideImage\" alt=\"Current reference image\" />
    </div>
    <div class=\"controls\">
      <div class=\"meta\">
        <span id=\"position\">Image 0 of 0</span>
        <span class=\"timer\" id=\"timer\">0s</span>
      </div>
      <div class=\"buttons\">
        <button id=\"backBtn\" type=\"button\">Back</button>
        <button id=\"pauseBtn\" type=\"button\">Pause</button>
        <button id=\"nextBtn\" type=\"button\">Next</button>
      </div>
    </div>
  </div>

  <script>
    const IMAGE_URLS = {{IMAGE_URLS_JSON}};
    const SECONDS_PER_IMAGE = {{SECONDS_PER_IMAGE}};

    let index = 0;
    let remaining = SECONDS_PER_IMAGE;
    let paused = false;

    const imageEl = document.getElementById('slideImage');
    const positionEl = document.getElementById('position');
    const timerEl = document.getElementById('timer');
    const pauseBtn = document.getElementById('pauseBtn');
    const backBtn = document.getElementById('backBtn');
    const nextBtn = document.getElementById('nextBtn');

    let renderToken = 0;

    async function resolveImageSource(imageUrl) {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.resolve_image === 'function') {
        try {
          return await window.pywebview.api.resolve_image(imageUrl);
        } catch (_err) {
          return imageUrl;
        }
      }
      return imageUrl;
    }

    async function updateView() {
      const token = ++renderToken;
      const imageUrl = IMAGE_URLS[index] || '';
      const resolvedSrc = imageUrl ? await resolveImageSource(imageUrl) : '';
      if (token !== renderToken) {
        return;
      }
      imageEl.src = resolvedSrc || '';
      positionEl.textContent = `Image ${index + 1} of ${IMAGE_URLS.length}`;
      timerEl.textContent = `${remaining}s`;
      pauseBtn.textContent = paused ? 'Resume' : 'Pause';
      backBtn.disabled = index === 0;
      nextBtn.disabled = IMAGE_URLS.length === 0;
    }

    function resetTimer() {
      remaining = SECONDS_PER_IMAGE;
    }

    function moveTo(newIndex) {
      if (IMAGE_URLS.length === 0) {
        return;
      }
      index = Math.max(0, Math.min(newIndex, IMAGE_URLS.length - 1));
      resetTimer();
      updateView();
    }

    function goNext(autoAdvance = false) {
      if (index < IMAGE_URLS.length - 1) {
        moveTo(index + 1);
      } else {
        // Stop when the final image countdown completes.
        remaining = 0;
        if (autoAdvance) {
          paused = true;
        }
        updateView();
      }
    }

    function goBack() {
      if (index > 0) {
        moveTo(index - 1);
      }
    }

    pauseBtn.addEventListener('click', () => {
      paused = !paused;
      updateView();
    });

    backBtn.addEventListener('click', () => {
      goBack();
    });

    nextBtn.addEventListener('click', () => {
      goNext(false);
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === ' ') {
        event.preventDefault();
        paused = !paused;
        updateView();
      } else if (event.key === 'ArrowRight') {
        goNext(false);
      } else if (event.key === 'ArrowLeft') {
        goBack();
      }
    });

    setInterval(() => {
      if (paused || IMAGE_URLS.length === 0) {
        return;
      }
      if (remaining > 0) {
        remaining -= 1;
      }
      if (remaining <= 0) {
        goNext(true);
      } else {
        updateView();
      }
    }, 1000);

    window.addEventListener('pywebviewready', () => {
      updateView();
    });

    updateView();
  </script>
</body>
</html>
"""

    html = html.replace("{{IMAGE_URLS_JSON}}", json.dumps(image_urls))
    html = html.replace("{{SECONDS_PER_IMAGE}}", str(seconds_per_image))

    api = SlideshowApi()
    webview.create_window("timeshow", html=html, width=1280, height=900, js_api=api)
    webview.start()


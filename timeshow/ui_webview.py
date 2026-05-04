#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import mimetypes
import os
from base64 import b64encode
from urllib.parse import unquote, urlparse

import webview

DEFAULT_SECONDS_PER_IMAGE = 120


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
        self._window = None

    def set_window(self, window):
        self._window = window

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

    def save_image_list(self, image_urls):
        if self._window is None:
            return {"ok": False, "error": "Window not ready."}
        try:
            dest = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="image_set.txt",
                file_types=("Text files (*.txt)", "All files (*.*)"),
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        if not dest:
            return {"ok": False, "cancelled": True}

        if isinstance(dest, (list, tuple)):
            dest = dest[0]

        try:
            lines = []
            for url in image_urls:
                path = _file_uri_to_path(url)
                lines.append(path if path else url)
            with open(dest, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as exc:
            return {"ok": False, "error": f"Could not write file: {exc}"}

        return {"ok": True}


class ConfigApi:
    def __init__(self, initial_config):
        self.initial_config = initial_config
        self.result = None
        self._window = None

    def set_window(self, window):
        self._window = window

    def get_initial_config(self):
        return self.initial_config

    def submit_config(self, config):
        if not isinstance(config, dict):
            return {"ok": False, "error": "Invalid configuration payload."}

        mode = str(config.get("mode", "")).strip()
        path = str(config.get("path", "")).strip()

        try:
            max_images = int(config.get("max_images", 0))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Maximum images must be an integer."}

        try:
            time_s = int(config.get("time_s", DEFAULT_SECONDS_PER_IMAGE))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Time must be an integer."}

        random_value = config.get("random_order", True)
        if isinstance(random_value, bool):
            random_order = random_value
        elif isinstance(random_value, str):
            random_order = random_value.strip().lower() in {"1", "true", "yes", "y"}
        else:
            random_order = bool(random_value)

        if not path:
            return {"ok": False, "error": "Please select or enter a path."}
        if time_s <= 0:
            return {"ok": False, "error": "Time must be a positive number of seconds."}
        if max_images < 0:
            return {"ok": False, "error": "Maximum images must be zero or higher."}

        self.result = {
            "mode": mode,
            "path": path,
            "time_s": time_s,
            "max_images": max_images,
            "random_order": random_order,
        }

        if self._window is not None:
            self._window.destroy()

        return {"ok": True}

    def cancel(self):
        self.result = None
        if self._window is not None:
            self._window.destroy()
        return {"ok": True}

    def pick_path(self, mode, current_path=""):
        if self._window is None:
            return {"ok": False, "error": "Window is not ready."}

        start_dir = ""
        if current_path:
            expanded = os.path.expanduser(str(current_path))
            if os.path.isdir(expanded):
                start_dir = expanded
            else:
                parent_dir = os.path.dirname(expanded)
                if os.path.isdir(parent_dir):
                    start_dir = parent_dir

        try:
            if mode == "url_index":
                selection = self._window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    directory=start_dir,
                    allow_multiple=False,
                    file_types=("Text files (*.txt;*.text)", "All files (*.*)"),
                )
            else:
                selection = self._window.create_file_dialog(
                    webview.FileDialog.FOLDER,
                    directory=start_dir,
                    allow_multiple=False,
                )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        if not selection:
            return {"ok": True, "path": ""}

        if isinstance(selection, (list, tuple)):
            selected_path = selection[0]
        else:
            selected_path = selection

        return {"ok": True, "path": selected_path}


def run_configuration_window(initial_config=None, error=None):
    defaults = {
        "mode": "shallow_dir",
        "path": "",
        "time_s": DEFAULT_SECONDS_PER_IMAGE,
        "max_images": 0,
        "random_order": True,
    }
    if initial_config:
        defaults.update(initial_config)

    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>timeshow configuration</title>
  <style>
    html, body {
      margin: 0;
      width: 100%;
      height: 100%;
      background: #111;
      color: #f0f0f0;
      font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;
    }
    .wrap {
      box-sizing: border-box;
      max-width: 760px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      margin: 0 0 12px;
      font-size: 22px;
      font-weight: 600;
    }
    .field {
      margin: 14px 0;
    }
    .field label {
      display: block;
      margin-bottom: 6px;
      font-size: 14px;
    }
    .row {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    input, select {
      background: #1f1f1f;
      border: 1px solid #444;
      color: #fff;
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 14px;
    }
    input[type=\"text\"] {
      width: min(100%, 520px);
    }
    input[type=\"number\"] {
      width: 120px;
    }
    .hint {
      color: #b9b9b9;
      font-size: 12px;
      margin-top: 6px;
    }
    .presets {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    button {
      border: 1px solid #555;
      background: #2b2b2b;
      color: #fff;
      border-radius: 6px;
      padding: 8px 14px;
      cursor: pointer;
      font-size: 14px;
    }
    button:hover {
      background: #3a3a3a;
    }
    .actions {
      margin-top: 18px;
      display: flex;
      gap: 10px;
    }
    .error {
      min-height: 20px;
      color: #ff8b8b;
      font-size: 13px;
      margin-top: 4px;
    }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>timeshow configuration</h1>
    <form id=\"configForm\">
      <div class=\"field\">
        <label for=\"modeSelect\">Mode</label>
        <select id=\"modeSelect\" required>
          <option value=\"shallow_dir\">shallow_dir</option>
          <option value=\"deep_dir\">deep_dir</option>
          <option value=\"url_index\">url_index</option>
        </select>
        <div class=\"hint\" id=\"modeHint\"></div>
      </div>

      <div class=\"field\">
        <label for=\"pathInput\">Path</label>
        <div class=\"row\">
          <input id=\"pathInput\" type=\"text\" placeholder=\"/path/to/images/or/index.txt\" required />
          <button id=\"browseBtn\" type=\"button\">Browse...</button>
        </div>
      </div>

      <div class=\"field\">
        <label>Time per image</label>
        <div class=\"row\">
          <input id=\"timeValue\" type=\"number\" min=\"1\" step=\"1\" required />
          <select id=\"timeUnit\">
            <option value=\"seconds\">Seconds</option>
            <option value=\"minutes\">Minutes</option>
          </select>
        </div>
        <div class=\"presets\">
          <label for=\"timePreset\">Preset</label>
          <select id=\"timePreset\">
            <option value=\"\">Choose preset...</option>
            <option value=\"30\">30 seconds</option>
            <option value=\"60\">1 minute</option>
            <option value=\"90\">90 seconds</option>
            <option value=\"120\">2 minutes</option>
            <option value=\"180\">3 minutes</option>
            <option value=\"300\">5 minutes</option>
            <option value=\"600\">10 minutes</option>
            <option value=\"900\">15 minutes</option>
            <option value=\"1200\">20 minutes</option>
            <option value=\"1800\">30 minutes</option>
          </select>
        </div>
      </div>

      <div class=\"field\">
        <label for=\"maxInput\">Maximum images (0 = no limit)</label>
        <input id=\"maxInput\" type=\"number\" min=\"0\" step=\"1\" />
      </div>

      <div class=\"field\">
        <label class=\"row\" for=\"randomInput\">
          <input id=\"randomInput\" type=\"checkbox\" />
          Random order
        </label>
      </div>

      <div class=\"error\" id=\"errorText\"></div>

      <div class=\"actions\">
        <button type=\"submit\">Start slideshow</button>
        <button id=\"cancelBtn\" type=\"button\">Cancel</button>
      </div>
    </form>
  </div>

  <script>
    const DEFAULT_CONFIG = {{DEFAULT_CONFIG_JSON}};
    const INITIAL_ERROR = {{INITIAL_ERROR_JSON}};

    const modeSelect = document.getElementById('modeSelect');
    const pathInput = document.getElementById('pathInput');
    const timeValue = document.getElementById('timeValue');
    const timeUnit = document.getElementById('timeUnit');
    const timePreset = document.getElementById('timePreset');
    const maxInput = document.getElementById('maxInput');
    const randomInput = document.getElementById('randomInput');
    const modeHint = document.getElementById('modeHint');
    const errorText = document.getElementById('errorText');
    const cancelBtn = document.getElementById('cancelBtn');
    const browseBtn = document.getElementById('browseBtn');

    function setModeHint(mode) {
      if (mode === 'url_index') {
        modeHint.textContent = 'Path should be a text file with one URL or file path per line.';
      } else if (mode === 'deep_dir') {
        modeHint.textContent = 'Path should be a directory. Images are searched recursively.';
      } else {
        modeHint.textContent = 'Path should be a directory. Only files in that directory are used.';
      }
    }

    function applySeconds(seconds) {
      if (seconds >= 60 && seconds % 60 === 0) {
        timeUnit.value = 'minutes';
        timeValue.value = String(seconds / 60);
      } else {
        timeUnit.value = 'seconds';
        timeValue.value = String(seconds);
      }
    }

    function getSecondsValue() {
      const raw = Number(timeValue.value);
      if (!Number.isFinite(raw) || raw <= 0) {
        return NaN;
      }
      if (timeUnit.value === 'minutes') {
        return Math.round(raw * 60);
      }
      return Math.round(raw);
    }

    function showError(message) {
      errorText.textContent = message || '';
    }

    modeSelect.addEventListener('change', () => {
      setModeHint(modeSelect.value);
    });

    timePreset.addEventListener('change', () => {
      const value = Number(timePreset.value);
      if (Number.isFinite(value) && value > 0) {
        applySeconds(value);
      }
    });

    cancelBtn.addEventListener('click', async () => {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.cancel === 'function') {
        await window.pywebview.api.cancel();
      }
    });

    browseBtn.addEventListener('click', async () => {
      showError('');
      if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.pick_path !== 'function') {
        showError('Path picker is not available.');
        return;
      }

      const response = await window.pywebview.api.pick_path(modeSelect.value, pathInput.value.trim());
      if (!response || !response.ok) {
        showError((response && response.error) || 'Unable to open path picker.');
        return;
      }
      if (response.path) {
        pathInput.value = String(response.path);
      }
    });

    document.getElementById('configForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      showError('');

      const timeSeconds = getSecondsValue();
      if (!Number.isFinite(timeSeconds) || timeSeconds <= 0) {
        showError('Time must be a positive value.');
        return;
      }

      const payload = {
        mode: modeSelect.value,
        path: pathInput.value.trim(),
        time_s: timeSeconds,
        max_images: Number(maxInput.value || 0),
        random_order: randomInput.checked,
      };

      if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.submit_config !== 'function') {
        showError('Configuration API is not available.');
        return;
      }

      const response = await window.pywebview.api.submit_config(payload);
      if (!response || !response.ok) {
        showError((response && response.error) || 'Unable to start slideshow.');
      }
    });

    modeSelect.value = DEFAULT_CONFIG.mode || 'shallow_dir';
    pathInput.value = DEFAULT_CONFIG.path || '';
    maxInput.value = String(DEFAULT_CONFIG.max_images ?? 0);
    randomInput.checked = Boolean(DEFAULT_CONFIG.random_order);
    applySeconds(Number(DEFAULT_CONFIG.time_s) || 120);
    setModeHint(modeSelect.value);
    if (INITIAL_ERROR) showError(INITIAL_ERROR);
  </script>
</body>
</html>
"""

    html = html.replace("{{DEFAULT_CONFIG_JSON}}", json.dumps(defaults))
    html = html.replace("{{INITIAL_ERROR_JSON}}", json.dumps(error or ""))
    api = ConfigApi(defaults)
    window = webview.create_window("timeshow setup", html=html, width=760, height=620, js_api=api)
    api.set_window(window)
    webview.start()
    return api.result


def run_slideshow_window(image_urls, time_s=None, mode=None):
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
      position: relative;
      overflow: hidden;
      min-height: 0;
    }

    #zoomWrapper {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      transform-origin: center center;
    }

    #slideImage {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      user-select: none;
      -webkit-user-drag: none;
      pointer-events: none;
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
      min-width: 44px;
    }

    .filename {
      width: 100%;
      text-align: center;
      font-size: 13px;
      color: #aaa;
      padding: 4px 0 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
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

    button:disabled {
      opacity: 0.35;
      cursor: default;
    }

    button:disabled:hover {
      background: #2b2b2b;
    }

    .btn-divider {
      width: 1px;
      height: 22px;
      background: #555;
      margin: 0 4px;
      align-self: center;
      flex-shrink: 0;
    }

    .export-area {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .export-status {
      font-size: 12px;
      color: #aaa;
    }
  </style>
</head>
<body>
  <div class=\"app\">
    <div class=\"stage\">
      <div id=\"zoomWrapper\">
        <img id=\"slideImage\" alt=\"Current reference image\" />
      </div>
    </div>
    <div class=\"controls\">
      <div class=\"meta\">
        <span id=\"position\">Image 0 of 0</span>
        <span class=\"timer\" id=\"timer\">0:00</span>
      </div>
      <div class=\"buttons\">
        <button id=\"backBtn\" type=\"button\">Back</button>
        <button id=\"pauseBtn\" type=\"button\">Pause</button>
        <button id=\"nextBtn\" type=\"button\">Next</button>
        <span class=\"btn-divider\"></span>
        <button id=\"zoomOutBtn\" type=\"button\" title=\"Zoom out (Ctrl/Cmd -)\">&#x2212;</button>
        <button id=\"zoomFitBtn\" type=\"button\" title=\"Zoom to fit (Ctrl/Cmd 0)\">Fit</button>
        <button id=\"zoomInBtn\" type=\"button\" title=\"Zoom in (Ctrl/Cmd +)\">+</button>
      </div>
      <div class=\"export-area\" id=\"exportArea\" style=\"display:none\">
        <button id=\"exportBtn\" type=\"button\">Export set\u2026</button>
        <span class=\"export-status\" id=\"exportStatus\"></span>
      </div>
      <span class=\"filename\" id=\"filename\"></span>
    </div>
  </div>

  <script>
    const IMAGE_URLS = {{IMAGE_URLS_JSON}};
    const SECONDS_PER_IMAGE = {{SECONDS_PER_IMAGE}};
    const MODE = {{MODE_JSON}};

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

    const isMac = /Mac/i.test(navigator.platform);

    const zoomWrapper = document.getElementById('zoomWrapper');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomFitBtn = document.getElementById('zoomFitBtn');

    const ZOOM_STEP = 1.5;
    const ZOOM_MIN = 1.0;
    const ZOOM_MAX = 8.0;

    let zoomLevel = 1.0;
    let panX = 0;
    let panY = 0;
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;

    function clampPan() {
      const maxX = zoomWrapper.clientWidth * (zoomLevel - 1) / 2;
      const maxY = zoomWrapper.clientHeight * (zoomLevel - 1) / 2;
      panX = Math.max(-maxX, Math.min(maxX, panX));
      panY = Math.max(-maxY, Math.min(maxY, panY));
    }

    function applyZoom() {
      zoomWrapper.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
      zoomWrapper.style.cursor = zoomLevel > 1 ? 'grab' : 'default';
      zoomOutBtn.disabled = zoomLevel <= ZOOM_MIN;
      zoomInBtn.disabled = zoomLevel >= ZOOM_MAX;
      zoomFitBtn.disabled = zoomLevel <= ZOOM_MIN;
    }

    function zoomIn() {
      zoomLevel = Math.min(zoomLevel * ZOOM_STEP, ZOOM_MAX);
      clampPan();
      applyZoom();
    }

    function zoomOut() {
      zoomLevel = Math.max(zoomLevel / ZOOM_STEP, ZOOM_MIN);
      if (zoomLevel <= ZOOM_MIN) {
        zoomLevel = ZOOM_MIN;
        panX = 0;
        panY = 0;
      }
      applyZoom();
    }

    function zoomFit() {
      zoomLevel = ZOOM_MIN;
      panX = 0;
      panY = 0;
      applyZoom();
    }

    zoomInBtn.addEventListener('click', zoomIn);
    zoomOutBtn.addEventListener('click', zoomOut);
    zoomFitBtn.addEventListener('click', zoomFit);

    zoomWrapper.addEventListener('mousedown', (event) => {
      if (zoomLevel <= ZOOM_MIN) return;
      isDragging = true;
      dragStartX = event.clientX - panX;
      dragStartY = event.clientY - panY;
      zoomWrapper.style.cursor = 'grabbing';
      event.preventDefault();
    });

    document.addEventListener('mousemove', (event) => {
      if (!isDragging) return;
      panX = event.clientX - dragStartX;
      panY = event.clientY - dragStartY;
      clampPan();
      zoomWrapper.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
      zoomWrapper.style.cursor = 'grabbing';
    });

    document.addEventListener('mouseup', () => {
      if (!isDragging) return;
      isDragging = false;
      zoomWrapper.style.cursor = zoomLevel > ZOOM_MIN ? 'grab' : 'default';
    });

    const filenameEl = document.getElementById('filename');
    const exportArea = document.getElementById('exportArea');
    const exportBtn = document.getElementById('exportBtn');
    const exportStatus = document.getElementById('exportStatus');

    if (MODE === 'shallow_dir' || MODE === 'deep_dir') {
      exportArea.style.display = 'flex';
    }

    exportBtn.addEventListener('click', async () => {
      const wasPaused = paused;
      paused = true;
      exportStatus.textContent = '';
      updateView();

      const response = await window.pywebview.api.save_image_list(IMAGE_URLS);

      if (!response || response.cancelled) {
        // user cancelled — restore silently
      } else if (!response.ok) {
        exportStatus.textContent = response.error || 'Save failed.';
      } else {
        exportStatus.textContent = 'Saved.';
        setTimeout(() => { exportStatus.textContent = ''; }, 3000);
      }

      paused = wasPaused;
      updateView();
    });

    function formatTime(seconds) {
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      return `${m}:${String(s).padStart(2, '0')}`;
    }

    function getFilename(url) {
      if (!url) return '';
      try {
        return decodeURIComponent(url).split('/').pop() || '';
      } catch (_) {
        return url.split('/').pop() || '';
      }
    }

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
      timerEl.textContent = formatTime(remaining);
      filenameEl.textContent = getFilename(imageUrl);
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
      zoomLevel = ZOOM_MIN;
      panX = 0;
      panY = 0;
      applyZoom();
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
      const mod = isMac ? event.metaKey : event.ctrlKey;
      if (mod && (event.key === '=' || event.key === '+')) {
        event.preventDefault();
        zoomIn();
      } else if (mod && event.key === '-') {
        event.preventDefault();
        zoomOut();
      } else if (mod && event.key === '0') {
        event.preventDefault();
        zoomFit();
      } else if (event.key === ' ') {
        event.preventDefault();
        paused = !paused;
        updateView();
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        goNext(false);
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
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

    applyZoom();
    updateView();
  </script>
</body>
</html>
"""

    html = html.replace("{{IMAGE_URLS_JSON}}", json.dumps(image_urls))
    html = html.replace("{{SECONDS_PER_IMAGE}}", str(seconds_per_image))
    html = html.replace("{{MODE_JSON}}", json.dumps(mode or ""))

    api = SlideshowApi()
    window = webview.create_window("timeshow", html=html, width=1280, height=900, js_api=api)
    api.set_window(window)
    webview.start()


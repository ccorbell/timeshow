#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from timeshow.imagecollector import ImageCollector
from timeshow.showmode import showmode_deep_dir, showmode_shallow_dir, showmode_url_index
from timeshow.ui_webview import run_configuration_window, run_slideshow_window
ARGPREFIX_MODE = "mode="
ARGPREFIX_TIME = "time="
ARGPREFIX_PATH = "path="
ARGPREFIX_MAX = "max="
ARGPREFIX_RANDOM = "random="

VALID_MODES = {
    showmode_shallow_dir,
    showmode_deep_dir,
    showmode_url_index,
}

USAGE_TEXT = f"""Usage:
  python3 -m timeshow.main mode=<mode> path=<path> [time=<seconds>] [max=<count>] [random=<true|false>]
  python3 -m timeshow.main [mode=<mode>] [time=<seconds>] [max=<count>] [random=<true|false>]   # opens GUI setup

Modes:
  {showmode_shallow_dir}  Show supported images directly inside path
  {showmode_deep_dir}     Recursively search for supported images under path
  {showmode_url_index}    Read image URLs/paths from a text file at path

Options:
  time=<seconds>          Seconds to show each image (default: {60})
  max=<count>             Limit the number of selected images (default: 0 = no limit)
  random=<true|false>     Shuffle selected images before showing them (default: true)
  -h, --help              Show this help text
"""


def print_usage(error_message=None):
    if error_message:
        print(f"Error: {error_message}", file=sys.stderr)
        print(file=sys.stderr)
        print(USAGE_TEXT, file=sys.stderr)
        return

    print(USAGE_TEXT)


def _parse_bool_arg(value):
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid random value '{value}'. Expected true or false.")


def _validate_inputs(mode, path, time_s, max_images):
    if mode not in VALID_MODES:
        valid_modes = ", ".join(sorted(VALID_MODES))
        return f"Invalid mode '{mode}'. Expected one of: {valid_modes}."

    if not path:
        return "Missing required path=<path> argument."

    if mode == showmode_url_index:
        if not os.path.isfile(path):
            return f"For mode '{showmode_url_index}', path must be an existing text file: {path}"
    else:
        if not os.path.isdir(path):
            return f"For mode '{mode}', path must be an existing directory: {path}"

    if time_s is not None and time_s <= 0:
        return "time must be a positive integer."

    if max_images < 0:
        return "max must be zero or a positive integer."

    return None

def timeshow_main(mode, path, time_s, max_images, random_order):
    runner = ImageCollector(mode, path)
    runner.locate_images()
    runner.select_images(random_order, max_images)
    if not runner.selected_images:
        if mode == showmode_url_index:
            print(f"No image URLs were read from {path}")
        else:
            print(f"No images were found in the directory at {path}")
        return

    run_slideshow_window(runner.selected_images, time_s)

    

if __name__ == '__main__':
    mode = "shallow_dir"
    path = None
    time_s = None
    max_images = 0
    random_order = True

    for arg in sys.argv[1:]:
        if arg in {"-h", "--help"}:
            print_usage()
            sys.exit(0)
        if arg.startswith(ARGPREFIX_MODE):
            mode = arg[len(ARGPREFIX_MODE):]
        elif arg.startswith(ARGPREFIX_TIME):
            time_value = arg[len(ARGPREFIX_TIME):]
            try:
                time_s = int(time_value)
            except ValueError:
                print_usage(f"Invalid time value '{time_value}'. Expected an integer.")
                sys.exit(1)
        elif arg.startswith(ARGPREFIX_PATH):
            path = arg[len(ARGPREFIX_PATH):]
        elif arg.startswith(ARGPREFIX_MAX):
            max_value = arg[len(ARGPREFIX_MAX):]
            try:
                max_images = int(max_value)
            except ValueError:
                print_usage(f"Invalid max value '{max_value}'. Expected an integer.")
                sys.exit(1)
        elif arg.startswith(ARGPREFIX_RANDOM):
            random_arg_value = arg[len(ARGPREFIX_RANDOM):]
            try:
                random_order = _parse_bool_arg(random_arg_value)
            except ValueError as exc:
                print_usage(str(exc))
                sys.exit(1)
        else:
            print_usage(f"Unknown argument '{arg}'.")
            sys.exit(1)

    if not path:
        config = run_configuration_window(
            {
                "mode": mode,
                "path": "",
                "time_s": time_s if time_s is not None else 60,
                "max_images": max_images,
                "random_order": random_order,
            }
        )
        if config is None:
            sys.exit(0)

        mode = config.get("mode", mode)
        path = config.get("path", path)
        time_s = config.get("time_s", time_s)
        max_images = config.get("max_images", max_images)
        random_order = config.get("random_order", random_order)

    validation_error = _validate_inputs(mode, path, time_s, max_images)
    if validation_error is not None:
        print_usage(validation_error)
        sys.exit(1)

    timeshow_main(mode, path, time_s, max_images, random_order)

# timeshow

Simple timed slideshow tool for artist reference practice.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python3 -m timeshow.main mode=shallow_dir path=/absolute/path/to/images time=60
```

If `path=` is omitted, timeshow opens a GUI configuration window where you can set mode, path, timing, random order, and max images.

Alternatively, you can use the shell script wrapper:

```bash
./bin/timeshow.sh mode=shallow_dir path=/absolute/path/to/images time=60
```

Modes:
- `mode=shallow_dir`: only files directly in `path`
- `mode=deep_dir`: recurse through subdirectories
- `mode=url_index`: `path` points to a text file with one URL or file path per line

Optional args:
- `max=50` limits how many images are selected
- `random=false` disables randomization

## UI Controls

- `Back` and `Next` move between images
- `Pause` / `Resume` toggles countdown
- Keyboard: `Space` pause/resume, `Left` previous, `Right` next


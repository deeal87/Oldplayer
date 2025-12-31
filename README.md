# Oldplayer

A KDE-friendly desktop player inspired by Winamp. It provides:

- A radio deck with the provided Top-100 list and editable stream URLs.
- The ability to add your own stations.
- A local video player.
- A Twitch/Web tab for streaming via embedded browser.

## Requirements

- Python 3.10+
- Qt for Python
  - `PyQt6`
  - `PyQt6-WebEngine`

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python -m oldplayer.main
```

## Notes

- The provided station list ships with `radio-browser://` placeholders. When you press **Play**, the app tries to resolve a real stream URL via radio-browser. You can also double-click the **Stream URL** column to paste your own link.
- Custom stations are stored at `~/.config/oldplayer/user_stations.json`.

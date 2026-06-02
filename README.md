# streamdock-n3-linux

Linux controller and diagnostics for the FHOOU/Mirabox Stream Dock N3.

The connected N3 identifies as USB `6603:1003` with product string `HOTSPOTEKUSB HID DEMO`. It exposes two useful Linux interfaces:

- `/dev/hidraw*`: vendor HID interface used by the official SDK for LCD images, brightness, and most button reports.
- `/dev/input/event*`: keyboard-style input interface used by some firmware modes for standard key/media events, including knob events on this setup.

The official StreamDock Device SDK supports Linux and N3, but the Python package install path did not include the native transport library here. For that reason the SDK source is vendored under `vendor/StreamDock`.

## Project Files

```text
streamdock-n3-linux.py             Main config-driven Linux controller.
streamdock-n3-linux.config.json    Labels, colors, and action commands.
streamdock-n3-gui.py               Native GTK4 GUI for editing the config.
streamdock-n3-gui.desktop          Desktop entry so the GUI shows in Walker.
streamdock-n3-probe.py             Simple SDK probe for device, LCD keys, and SDK events.
streamdock-n3-debug.py             Raw hidraw + evdev diagnostic tool.
99-streamdock.rules                udev permissions for hidraw and input event nodes.
install_udev.sh                    Installs and reloads the udev rule.
streamdock-n3-linux.service        systemd user service template.
vendor/StreamDock/                 Vendored official Python SDK source and native transport.
docs/                              Screenshots used in this README.
```

## Requirements

- Linux with the Stream Dock N3 connected over USB.
- `uv` for Python environment management.
- Python dependencies from `pyproject.toml`: `pillow`, `pyudev`, `evdev`.
- Optional command-line tools used by the default config: `alacritty`, `chromium`, `xdg-open`, `obs`, `hyprctl`, `wpctl`, `playerctl`.

## Setup

Install device permissions:

```bash
cd /home/asad/Documents/projects/streamdock-n3-linux
./install_udev.sh
```

Then unplug and replug the Stream Dock.

The udev rule grants user access to both Stream Dock HID paths:

```text
/dev/hidraw*
/dev/input/event*
```

This matters because the screen/buttons and knob/media-style events may arrive through different Linux interfaces.

## Run The Controller

Start the controller:

```bash
UV_CACHE_DIR=.uv-cache uv run python streamdock-n3-linux.py
```

Test without executing commands:

```bash
UV_CACHE_DIR=.uv-cache uv run python streamdock-n3-linux.py --dry-run
```

Useful flags:

```text
--config PATH       Use a different JSON config.
--brightness N      Override configured brightness, 0-100.
--dry-run           Print actions without running commands.
--no-icons          Do not update LCD key images.
--no-init           Skip SDK initialization.
--seconds N         Exit after N seconds; useful for tests.
```

## GUI

`streamdock-n3-gui.py` is a single-window GTK4 utility for editing the controller config without touching JSON. It styles itself from the active Omarchy theme by parsing `~/.config/omarchy/current/theme/colors.toml` and re-applies CSS live when the theme changes.

| Status | Keys | Actions |
|---|---|---|
| ![Status tab](docs/screenshot-status.png) | ![Keys tab](docs/screenshot-keys.png) | ![Actions tab](docs/screenshot-actions.png) |

Run it directly:

```bash
python3 streamdock-n3-gui.py
```

Or install the desktop entry so it shows in Walker / app launchers:

```bash
cp streamdock-n3-gui.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

What it does:

- **Status tab** detects the dock via `/sys/bus/usb/devices` (no `lsusb` needed), installs the systemd user service on demand, and exposes Start / Restart / Stop plus a brightness slider.
- **Keys tab** has one card per LCD key. Each key is either:
  - **Label** mode — text + background color used to generate the LCD icon.
  - **Image** mode — a path to a custom image (center-cropped to square).
  - Or click **Pick app…** to choose any installed `.desktop` application; the GUI rasterises its icon to `~/.cache/streamdock-n3-linux/icons/` and fills the press command from the app's `Exec` line.
- **Actions tab** edits the three round-button and three-knob (left / right / press) command mappings.

Save writes back to `streamdock-n3-linux.config.json` and, if the service is active, restarts it. Logs go to `/tmp/streamdock-n3-gui.log`.

`--tab N` (0, 1, 2) opens the window directly on Status / Keys / Actions.

## Configuration

The controller reads [streamdock-n3-linux.config.json](streamdock-n3-linux.config.json).

Top-level fields:

```json
{
  "brightness": 80,
  "keys": {},
  "actions": {}
}
```

`keys` controls the six LCD labels:

```json
"1": { "label": "Term", "color": "#1c63b8" }
```

Supported key fields:

```text
label    Text rendered into a generated LCD icon.
color    Hex background color for the generated icon.
icon     Optional custom image path. If present and valid, it is used instead.
```

`actions` maps event names to shell commands:

```json
"button.1.press": "alacritty"
```

Actions can be a command string or a list of command strings.

## Event Names

SDK/HID event names:

```text
button.1.press through button.9.press
button.1.release through button.9.release
knob.1.left, knob.1.right, knob.1.press, knob.1.release
knob.2.left, knob.2.right, knob.2.press, knob.2.release
knob.3.left, knob.3.right, knob.3.press, knob.3.release
```

Evdev fallback event names:

```text
evdev.KEY_NAME.press
evdev.KEY_NAME.release
evdev.KEY_NAME.repeat
```

Examples:

```json
"evdev.KEY_VOLUMEUP.press": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+",
"evdev.KEY_VOLUMEDOWN.press": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"
```

## Default Mapping

Current default LCD key actions:

```text
1  Term   alacritty
2  Web    chromium
3  Files  xdg-open "$HOME"
4  OBS    obs
5  Mute   wpctl speaker mute toggle
6  Play   playerctl play-pause
```

Current default round button actions:

```text
7  Hyprland workspace 1
8  Hyprland workspace 2
9  Hyprland workspace 3
```

Current default knob actions:

```text
knob 1  speaker volume down/up, press to mute output
knob 2  media previous/next, press to play/pause
knob 3  microphone volume down/up, press to mute input
```

The config also includes standard evdev media-key fallbacks:

```text
KEY_VOLUMEUP
KEY_VOLUMEDOWN
KEY_MUTE
KEY_PREVIOUSSONG
KEY_NEXTSONG
KEY_PLAYPAUSE
```

## Diagnostics

Probe the official SDK path:

```bash
UV_CACHE_DIR=.uv-cache uv run python streamdock-n3-probe.py --no-icons --map
```

Run raw input diagnostics:

```bash
UV_CACHE_DIR=.uv-cache uv run python streamdock-n3-debug.py --seconds 20
```

While it runs, press:

```text
six LCD keys
three round buttons
all knob presses
all knob rotations in both directions
```

Expected diagnostic output can include:

```text
hidraw /dev/hidraw0: ...
evdev /dev/input/event6: KEY_... value=1
```

If you see an `evdev.KEY_...` name that is not in `streamdock-n3-linux.config.json`, add it under `actions`.

## Troubleshooting

If buttons do not print:

```bash
./install_udev.sh
```

Then unplug and replug the dock.

Check permissions:

```bash
ls -l /dev/hidraw* /dev/input/event*
```

If knobs do not print, run:

```bash
UV_CACHE_DIR=.uv-cache uv run python streamdock-n3-debug.py --seconds 20
```

The knobs may be on `/dev/input/event*`, not the SDK/hidraw callback. The updated udev rule includes:

```text
SUBSYSTEM=="input", KERNEL=="event*", ATTRS{idVendor}=="6603", MODE="0666", TAG+="uaccess"
```

If the controller starts but commands do not do what you expect, run with:

```bash
UV_CACHE_DIR=.uv-cache uv run python streamdock-n3-linux.py --dry-run
```

This prints the event and command without executing it.

## Autostart

Install the systemd user service:

```bash
mkdir -p ~/.config/systemd/user
cp streamdock-n3-linux.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now streamdock-n3-linux.service
```

View logs:

```bash
journalctl --user -u streamdock-n3-linux.service -f
```

The service currently assumes this project path:

```text
/home/asad/Documents/projects/streamdock-n3-linux
```

## Known Limitations

- This is not a full clone of the Windows/macOS Stream Dock software UI.
- Profiles, folders, OBS integration UI, and macro editing are not implemented yet.
- Actions are shell commands in JSON.
- Knob event names may vary by firmware mode. Use `streamdock-n3-debug.py` to confirm exact `evdev.KEY_...` names.
- The vendored SDK is copied from the official StreamDock Device SDK because the packaged install path did not include the Linux native transport library in this environment.

# Changelog

## 2026-06-02

### Added

- Created a fresh Linux project for the FHOOU/Mirabox Stream Dock N3.
- Identified the connected device as USB `6603:1003`, product `HOTSPOTEKUSB HID DEMO`.
- Confirmed the N3 exposes two HID interfaces:
  - vendor-defined hidraw interface for SDK control.
  - keyboard/input interface for Linux input events.
- Vendored the official StreamDock Python SDK under `vendor/StreamDock`.
- Added `pyproject.toml` and `uv.lock` for Python dependency management.
- Added `streamdock-n3-probe.py`:
  - enumerates the N3.
  - initializes the device.
  - sets test LCD icons.
  - prints SDK-decoded input events.
- Added `streamdock-n3-linux.py`:
  - reads `streamdock-n3-linux.config.json`.
  - sets LCD labels/colors.
  - listens for SDK/HID events.
  - listens for evdev fallback events.
  - executes mapped shell commands.
  - supports dry-run mode.
- Added `streamdock-n3-linux.config.json` with default mappings:
  - LCD keys for terminal, browser, files, OBS, mute, play/pause.
  - round buttons for Hyprland workspaces 1-3.
  - knob mappings for volume, media, and microphone controls.
  - evdev media-key fallback mappings.
- Added `streamdock-n3-debug.py`:
  - monitors Stream Dock hidraw reports.
  - monitors Stream Dock evdev keyboard events.
  - helps discover exact event names.
- Added `99-streamdock.rules` for user access to:
  - Stream Dock USB device.
  - Stream Dock hidraw nodes.
  - Stream Dock input event nodes.
- Added `install_udev.sh` to install and reload udev rules.
- Added `streamdock-n3-linux.service` for systemd user autostart.
- Added `.gitignore` for generated icons, uv cache, virtualenv, and Python bytecode.

### Changed

- Replaced the initial probe-only setup with a config-driven controller.
- Updated event output to use human-readable names:
  - `lcd key 1` through `lcd key 6`.
  - `round button 1` through `round button 3`.
  - `small knob 1`, `small knob 2`, `large knob`.
- Updated udev rules after discovering that knob/input events may use `/dev/input/event*`, not only `/dev/hidraw*`.
- Updated the systemd service to use the local `uv` path and `UV_CACHE_DIR=.uv-cache`.
- Reworked README into full current-project documentation.

### Verified

- The SDK can enumerate the N3.
- The SDK can open the device through hidraw.
- LCD key image writes return success for the six visual keys.
- Button permissions work after udev rule installation.
- The controller starts and warns clearly when hidraw or input event permissions are missing.
- The debug script can identify permission problems for `/dev/input/event6`.

### Known Issues

- Exact knob rotation event names still need final confirmation from `streamdock-n3-debug.py` output after the updated udev rule is installed and the dock is replugged.
- This project currently uses shell-command actions only; no graphical profile editor exists.
- The official SDK is vendored because the Python package install path did not include the required native Linux transport library in this environment.

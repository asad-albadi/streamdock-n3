# Changelog

## 0.2.5 — 2026-06-03

### Fixed

- Move the root-pycache guard from `system_install.py` to the package's `__init__.py`, gated on `os.geteuid() == 0`. The previous placement was too late — by the time `system_install`'s body executed, Python had already compiled and emitted `streamdock_n3/__init__.pyc` as root, dropping root-owned files into the user's pipx venv. The next user-mode `pipx install --force` then failed with `Permission denied` on `__pycache__`. With the guard at package init, `sys.dont_write_bytecode` is set before any submodule .pyc gets emitted, so re-running the install one-liner now upgrades cleanly without manual `sudo rm`.

## 0.2.4 — 2026-06-03

### Fixed

- `install.sh` now `systemctl --user restart`s the service after installation instead of `enable --now`. The old command was a no-op when the service was already running, so re-running the one-liner to upgrade silently kept the previous binary live. With `restart`, the same `curl … | bash` command works for both fresh installs and upgrades.

## 0.2.3 — 2026-06-03

### Fixed

- Daemon shutdown no longer emits `tcache_thread_shutdown(): unaligned tcache chunk detected` followed by a SIGABRT core dump. The vendored SDK's `libtransport.so` has a broken thread-cleanup path; joining its reader/heartbeat threads in `device.close()` triggers glibc's tcache integrity check. The daemon now skips `device.close()` and `os._exit()`s past Python's interpreter finalization, so the kernel reclaims the HID file descriptor cleanly and systemd sees a normal exit code.

### Changed

- Removed the obsolete repo-root `streamdock-n3-linux.config.json`. The runtime config lives at `$XDG_CONFIG_HOME/streamdock-n3/config.json`; the file at the repo root was only kept as a historical reference and is no longer needed.
- CI and release workflows bumped to `actions/checkout@v5` and `astral-sh/setup-uv@v6` so GitHub stops complaining about the Node 20 deprecation.

## 0.2.2 — 2026-06-02

### Changed

- `install.sh` now hard-requires `pipx` and exits with a per-distro install hint if missing, instead of silently falling back to `uv tool install` or `pip --user`. Those fallbacks ship a venv that cannot import the distro's `python-gobject`, so the GUI entry point crashes at startup. Failing fast with a clear message is better than a half-broken install.

## 0.2.1 — 2026-06-02

### Changed

- `install.sh` no longer prints a redundant "Next steps" block — the script now runs `systemctl --user daemon-reload` and `systemctl --user enable --now streamdock-n3.service` itself, so the curl|bash one-liner is zero-touch after the sudo prompt.
- README title is now "Stream Dock N3 for Linux" with a one-line description of what the project actually does, instead of just repeating the repo name.

## 0.2.0 — 2026-06-02 — packaging

### Added

- Restructured the project as a proper Python package under `src/streamdock_n3/` with a `hatchling` build backend.
- Console entry points: `streamdock-n3`, `streamdock-n3-gui`, `streamdock-n3-probe`, `streamdock-n3-debug`, `streamdock-n3-install`.
- `streamdock-n3-install`: idempotent installer for the udev rule, systemd user unit, and desktop entry. Templates `@BIN@` based on the actual installed binary location.
- XDG-compliant runtime layout: config at `$XDG_CONFIG_HOME/streamdock-n3/config.json`, icon cache at `$XDG_CACHE_HOME/streamdock-n3/`, GUI log at `$XDG_STATE_HOME/streamdock-n3/gui.log`. Config is seeded with a default on first run.
- `install.sh`: one-shot end-user installer that fetches the latest GitHub Release wheel and runs `pipx install` + `sudo streamdock-n3-install`.
- `Makefile`: distro-packager-friendly `install` / `install-data` / `uninstall` targets honouring `DESTDIR` and `PREFIX`.
- GitHub Actions: `ci.yml` (ruff, mypy, pytest, build smoke) and `release.yml` (tag-triggered wheel + sdist + SHA256SUMS published to a GitHub Release).
- Unit tests under `tests/` covering events, icons, config IO, and Exec-code stripping.
- `LICENSE` (MIT).

### Changed

- Daemon, GUI, probe, and debug-tool scripts were converted to package modules with `main()` entry points; old hyphenated `.py` scripts at the repo root no longer exist.
- GUI's "Install service" button now calls `pkexec streamdock-n3-install` instead of copying a service file out of the project directory.
- Service unit description tightened, hard-coded `WorkingDirectory` removed, `ExecStart` switched to the installed binary.
- Desktop entry `Exec=` switched to the installed `streamdock-n3-gui` binary.
- GTK `application_id` changed to `io.github.asad_albadi.StreamDockN3` (was Vodafone-internal).
- `streamdock-n3-linux.config.json` at the repo root is no longer a runtime file; see `_data/config.default.json` for the seeded defaults.

### Removed

- `install_udev.sh` (replaced by `streamdock-n3-install`).
- Top-level hyphenated `.py` scripts (`streamdock-n3-linux.py`, etc.) — replaced by package modules + entry points.

### Notes

- The GUI requires `python-gobject` (PyGObject), which is provided by the distro and not reliably pip-installable. `install.sh` therefore uses `pipx install --system-site-packages`; manual installs should do the same. Daemon and probe/debug entry points have no such requirement.
- Users with an existing repo-root `streamdock-n3-linux.config.json` should copy it to `~/.config/streamdock-n3/config.json` to preserve customizations; a fresh default is seeded if none exists.

## 2026-06-02 — GUI

### Added

- Added `streamdock-n3-gui.py`, a native GTK4 desktop utility for editing the controller config.
  - Status tab: USB device detection via sysfs (no `lsusb` dependency), systemd user service install/start/restart/stop, brightness slider.
  - Keys tab: per-LCD-key card with square preview, segmented Label / Image mode toggle, color picker, and a "Pick app…" button that scans installed `.desktop` files and assigns the chosen app's icon and `Exec` command in one step.
  - Actions tab: editors for the three round buttons and the three knobs (left, right, press).
  - Toast notifications for save, reload, and service actions.
  - File diagnostics written to `/tmp/streamdock-n3-gui.log`.
- Added `streamdock-n3-gui.desktop` so the utility appears in Walker and other app launchers.
- Theming: the GUI parses `~/.config/omarchy/current/theme/colors.toml` and rebuilds its CSS from the active Omarchy palette, watching the file with `Gio.FileMonitor` so theme switches re-style the app live.
- Application icons selected through "Pick app…" are rasterised to 144×144 PNGs cached under `~/.cache/streamdock-n3-linux/icons/`, so the controller's PIL pipeline works with apps that ship SVG icons.
- Added `--tab N` CLI flag to launch the GUI on a specific tab (used for screenshots).
- Added `docs/` with screenshots of the Status, Keys, and Actions tabs.

### Changed

- README now documents the GUI alongside the CLI controller and embeds the screenshots.

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

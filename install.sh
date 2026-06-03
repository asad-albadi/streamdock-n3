#!/usr/bin/env bash
# One-shot installer for streamdock-n3-linux from GitHub Releases.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/asad-albadi/streamdock-n3/master/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/asad-albadi/streamdock-n3/master/install.sh | bash -s -- --version v0.2.0
#
# Flags:
#   --version vX.Y.Z   pin to a specific release tag (default: latest)
#   --no-system        skip the sudo step that installs udev/service/desktop

set -euo pipefail

REPO="asad-albadi/streamdock-n3"
VERSION="latest"
DO_SYSTEM=1

while [ $# -gt 0 ]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        --no-system) DO_SYSTEM=0; shift ;;
        *) echo "unknown flag: $1" >&2; exit 2 ;;
    esac
done

need() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "missing required command: $1" >&2
        exit 1
    }
}

need curl
need python3

# Require pipx. The GUI needs the system-provided python-gobject (the `gi`
# binding), which is not reliably pip-installable. pipx with
# --system-site-packages is the only path that consistently exposes it to the
# entry-point venv. uv tool / pip --user fallbacks either lose `gi` access or
# clash with PEP 668, so we exit early with a clear install hint instead.
if ! command -v pipx >/dev/null 2>&1; then
    cat <<'EOF' >&2
error: `pipx` is required to install streamdock-n3-linux.

Install it for your distribution, then re-run this script:

    Arch / Omarchy:   sudo pacman -S python-pipx
    Debian / Ubuntu:  sudo apt install pipx
    Fedora:           sudo dnf install pipx
    openSUSE:         sudo zypper install python3-pipx
    macOS (Homebrew): brew install pipx
    Any system:       python3 -m pip install --user --break-system-packages pipx

Why pipx? The GUI imports the distro-provided python-gobject (GTK4 binding),
which a vanilla pip install cannot expose. pipx with --system-site-packages
gives the entry-point venv access to it while still keeping the install
isolated from your system Python.
EOF
    exit 1
fi

PY_INSTALL=(pipx install --force --system-site-packages)

# Resolve the wheel URL.
if [ "$VERSION" = "latest" ]; then
    RELEASE_API="https://api.github.com/repos/${REPO}/releases/latest"
else
    RELEASE_API="https://api.github.com/repos/${REPO}/releases/tags/${VERSION}"
fi

echo "querying $RELEASE_API"
WHEEL_URL=$(
    curl -fsSL "$RELEASE_API" \
        | python3 -c '
import json, sys
data = json.load(sys.stdin)
wheels = [a["browser_download_url"] for a in data["assets"]
          if a["name"].endswith(".whl")]
if not wheels:
    sys.exit("no wheel asset in release")
print(wheels[0])
'
)

echo "installing wheel: $WHEEL_URL"
"${PY_INSTALL[@]}" "$WHEEL_URL"

if [ "$DO_SYSTEM" -eq 1 ]; then
    if ! command -v streamdock-n3-install >/dev/null 2>&1; then
        echo "streamdock-n3-install not on PATH; system install skipped." >&2
        echo "If using pip --user, ensure ~/.local/bin is on PATH and rerun:" >&2
        echo "  sudo streamdock-n3-install" >&2
        exit 0
    fi

    echo "running: sudo streamdock-n3-install"
    sudo "$(command -v streamdock-n3-install)"

    # streamdock-n3-install already reloads udev and applies the rule to the
    # currently-plugged-in device; we still need a systemd --user reload and
    # an enable+restart so a fresh install starts the service AND an upgrade
    # actually picks up the new binary (enable --now is a no-op if already
    # running, which would silently keep the old version live).
    systemctl --user daemon-reload
    systemctl --user enable streamdock-n3.service >/dev/null 2>&1 || true
    if systemctl --user restart streamdock-n3.service; then
        echo
        echo "streamdock-n3.service is enabled and running on the new wheel."
        echo "If buttons don't respond, unplug+replug the dock once."
    else
        echo
        echo "Service install succeeded but restart failed (see"
        echo "systemctl --user status streamdock-n3.service). Try unplugging"
        echo "and replugging the dock, then re-run the restart command."
    fi
else
    echo "skipped system install (udev/service/desktop)."
fi

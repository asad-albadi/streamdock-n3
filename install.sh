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

# Pick an installer: prefer pipx, fall back to pip --user.
if command -v pipx >/dev/null 2>&1; then
    PY_INSTALL=(pipx install --force)
else
    echo "pipx not found; falling back to pip --user (you should install pipx)" >&2
    PY_INSTALL=(python3 -m pip install --user --upgrade --break-system-packages)
fi

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
    else
        echo "running: sudo streamdock-n3-install"
        sudo "$(command -v streamdock-n3-install)"
    fi

    cat <<'EOF'

Next steps:
  1) Unplug and replug the Stream Dock so udev rules apply.
  2) systemctl --user daemon-reload
  3) systemctl --user enable --now streamdock-n3.service
EOF
else
    echo "skipped system install (udev/service/desktop)."
fi

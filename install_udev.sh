#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

sudo cp 99-streamdock.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --attr-match=idVendor=6603 || true

echo "Installed StreamDock udev rules."
echo "Unplug and replug the Stream Dock N3, then run:"
echo "  UV_CACHE_DIR=.uv-cache uv run python streamdock-n3-debug.py --seconds 20"

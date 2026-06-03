"""Install udev rule, systemd user unit, and desktop entry to system paths.

Run with `streamdock-n3-install`. Requires root (use sudo). The user-level
systemctl --user enable step is left to the caller, since this script may run
under sudo where the user session is not available.
"""

from __future__ import annotations

# The root-pycache guard lives in streamdock_n3/__init__.py — by the time
# any submodule body runs, sibling __init__.pyc has already been emitted,
# so the suppression must happen at package import.
import argparse
import os
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

UDEV_DST = Path("/etc/udev/rules.d/99-streamdock.rules")
SERVICE_DST = Path("/usr/lib/systemd/user/streamdock-n3.service")
DESKTOP_DST = Path("/usr/share/applications/streamdock-n3-gui.desktop")


def _data(name: str) -> Path:
    ref = resources.files("streamdock_n3").joinpath(f"_data/{name}")
    with resources.as_file(ref) as p:
        if not Path(p).is_file():
            raise FileNotFoundError(f"missing packaged data file: {name}")
        return Path(p)


def _resolve_bin_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    # 1. Trust our own argv[0]: the sibling `streamdock-n3` lives next to us.
    #    This survives `sudo` where the invoking user's PATH is not inherited.
    self_dir = Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else None
    if self_dir and (self_dir / "streamdock-n3").exists():
        return self_dir
    # 2. Fall back to PATH lookup.
    found = shutil.which("streamdock-n3")
    if found:
        return Path(found).resolve().parent
    # 3. Last resort.
    return Path("/usr/bin")


def _render(template: Path, bin_dir: Path) -> str:
    return template.read_text(encoding="utf-8").replace("@BIN@", str(bin_dir))


def _install_file(content: str, dst: Path, mode: int = 0o644) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, dst)


def _copy(src: Path, dst: Path, mode: int = 0o644) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    os.chmod(dst, mode)


def _reload_udev() -> None:
    for cmd in (
        ["udevadm", "control", "--reload-rules"],
        ["udevadm", "trigger", "--attr-match=idVendor=6603"],
    ):
        try:
            subprocess.run(cmd, check=False)
        except FileNotFoundError:
            print(f"warning: {cmd[0]} not found; skipping {' '.join(cmd[1:])}")


def install(bin_dir: Path) -> None:
    print(f"using binary directory: {bin_dir}")
    print(f"installing udev rule -> {UDEV_DST}")
    _copy(_data("99-streamdock.rules"), UDEV_DST)
    print(f"installing systemd user unit -> {SERVICE_DST}")
    _install_file(_render(_data("streamdock-n3.service"), bin_dir), SERVICE_DST)
    print(f"installing desktop entry -> {DESKTOP_DST}")
    _install_file(_render(_data("streamdock-n3-gui.desktop"), bin_dir), DESKTOP_DST)
    print("reloading udev")
    _reload_udev()
    print()
    print("Installed. Next steps:")
    print("  1) Unplug and replug the Stream Dock so udev rules apply.")
    print("  2) systemctl --user daemon-reload")
    print("  3) systemctl --user enable --now streamdock-n3.service")


def uninstall() -> None:
    for target in (UDEV_DST, SERVICE_DST, DESKTOP_DST):
        if target.exists():
            print(f"removing {target}")
            target.unlink()
    _reload_udev()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="streamdock-n3-install")
    parser.add_argument(
        "--bin-dir",
        help="Directory where streamdock-n3 entry points live "
        "(default: parent of `which streamdock-n3`, else /usr/bin).",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the installed udev rule, service, and desktop file.",
    )
    args = parser.parse_args(argv)

    if os.geteuid() != 0:
        print("error: streamdock-n3-install must run as root (use sudo).", file=sys.stderr)
        return 1

    if args.uninstall:
        uninstall()
        return 0

    install(_resolve_bin_dir(args.bin_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

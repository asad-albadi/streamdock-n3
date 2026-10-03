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
from collections.abc import Callable
from importlib import resources
from pathlib import Path

UDEV_DST = Path("/etc/udev/rules.d/99-streamdock.rules")
SERVICE_DST = Path("/usr/lib/systemd/user/streamdock-n3.service")
DESKTOP_DST = Path("/usr/share/applications/streamdock-n3-gui.desktop")
USB_DEVICES_DIR = Path("/sys/bus/usb/devices")
DEVICE_RULES = {
    "mirabox": ("Mirabox", "6603", "99-streamdock-mirabox.rules"),
    "hotspotekusb": ("HOTSPOTEKUSB", "5548", "99-streamdock-hotspotekusb.rules"),
}


def _data_text(name: str) -> str:
    """Return a packaged data file's contents.

    Reads through the Traversable rather than resources.as_file, whose
    extracted temp file is unlinked once its context exits — a path handed out
    from inside that context is already gone when the caller opens it.
    """
    ref = resources.files("streamdock_n3").joinpath(f"_data/{name}")
    try:
        return ref.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise FileNotFoundError(f"missing packaged data file: {name}") from exc


def _purge_root_owned_bytecode() -> None:
    """Delete root-owned bytecode this process just wrote into a user venv.

    The guard in streamdock_n3/__init__.py sets sys.dont_write_bytecode, which
    covers every submodule, but it cannot cover __init__ itself: CPython writes
    a module's .pyc before executing its body, so __init__.cpython-*.pyc is
    already on disk as root by the time the guard runs.

    One root-owned file inside a user-owned pipx venv is enough to make every
    later upgrade fail -- `uv venv --clear` and `pipx install --force` both hit
    EACCES trying to remove the tree, and pipx then crashes on its own trash
    directory. So clean up after ourselves instead of leaving a landmine.

    Scoped to the whole virtualenv, not just this package: the venv's own
    _virtualenv.py shim is imported at interpreter startup, before this package
    exists, so it too lands in site-packages as root and blocks removal of lib/
    just as effectively.

    Skipped when the tree is itself root-owned: that is a system-wide install
    (the Makefile path), where root owning the bytecode is correct and removing
    it would be vandalism.
    """
    try:
        import streamdock_n3

        pkg_dir = Path(streamdock_n3.__file__).resolve().parent
        scope = pkg_dir
        for parent in pkg_dir.parents:
            if (parent / "pyvenv.cfg").is_file():
                scope = parent
                break
        if scope.stat().st_uid == 0:
            return
        removed = 0
        for cache in sorted(scope.rglob("__pycache__"), reverse=True):
            for entry in list(cache.iterdir()):
                if entry.is_file() and entry.stat().st_uid == 0:
                    entry.unlink()
                    removed += 1
            if cache.stat().st_uid == 0 and not any(cache.iterdir()):
                cache.rmdir()
        if removed:
            print(f"cleaned {removed} root-owned bytecode file(s) under {scope}")
    except (OSError, ImportError) as exc:
        print(
            f"warning: could not clean root-owned bytecode: {exc}\n"
            "If a later upgrade fails with 'Permission denied', remove the venv "
            "with sudo and reinstall.",
            file=sys.stderr,
        )


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


def _render(template: str, bin_dir: Path) -> str:
    return template.replace("@BIN@", str(bin_dir))


def _install_file(content: str, dst: Path, mode: int = 0o644) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, dst)


def detect_connected_devices(root: Path = USB_DEVICES_DIR) -> tuple[str, ...]:
    """Return supported device keys currently present on the USB bus."""
    vendors: set[str] = set()
    try:
        for vendor_file in root.glob("*/idVendor"):
            try:
                vendors.add(vendor_file.read_text(encoding="ascii").strip().lower())
            except OSError:
                continue
    except OSError:
        return ()
    return tuple(
        key
        for key, (_label, vendor_id, _rule) in DEVICE_RULES.items()
        if vendor_id in vendors
    )


def select_device(
    device: str | None = None,
    *,
    input_fn: Callable[[str], str] | None = None,
) -> str:
    """Ask which rule to install, defaulting to the sole detected device."""
    if device is not None:
        if device not in DEVICE_RULES:
            raise ValueError(f"unsupported device: {device}")
        return device

    detected = detect_connected_devices()
    default = detected[0] if len(detected) == 1 else None
    if detected:
        labels = ", ".join(DEVICE_RULES[key][0] for key in detected)
        print(f"Detected USB device(s): {labels}")
    else:
        print("No supported Stream Dock detected over USB.")

    if input_fn is None:
        input_fn = input
    for key, (label, _vendor_id, _rule) in DEVICE_RULES.items():
        if key == default:
            marker = " (detected, default)"
        elif key in detected:
            marker = " (detected)"
        else:
            marker = ""
        print(f"  {1 if key == 'mirabox' else 2}) {label}{marker}")
    prompt = "Select device [1/2]"
    if default:
        prompt += f" (Enter = {DEVICE_RULES[default][0]})"
    prompt += ": "

    while True:
        answer = input_fn(prompt).strip().lower()
        if not answer and default:
            return default
        if answer in ("1", "mirabox", "m"):
            return "mirabox"
        if answer in ("2", "hotspotekusb", "hotspot", "h"):
            return "hotspotekusb"
        print("Please enter 1 or 2.")


def _reload_udev(vendor_id: str | None = None) -> None:
    commands = [["udevadm", "control", "--reload-rules"]]
    vendor_ids = (vendor_id,) if vendor_id else tuple(
        details[1] for details in DEVICE_RULES.values()
    )
    commands.extend(
        ["udevadm", "trigger", f"--attr-match=idVendor={vid}"]
        for vid in vendor_ids
    )
    for cmd in commands:
        try:
            subprocess.run(cmd, check=False)
        except FileNotFoundError:
            print(f"warning: {cmd[0]} not found; skipping {' '.join(cmd[1:])}")


def install(bin_dir: Path, device: str) -> None:
    if device not in DEVICE_RULES:
        raise ValueError(f"unsupported device: {device}")
    label, vendor_id, rule_file = DEVICE_RULES[device]
    print(f"using binary directory: {bin_dir}")
    print(f"installing udev rule -> {UDEV_DST}")
    print(f"selected device: {label}")
    _install_file(_data_text(rule_file), UDEV_DST)
    print(f"installing systemd user unit -> {SERVICE_DST}")
    _install_file(_render(_data_text("streamdock-n3.service"), bin_dir), SERVICE_DST)
    print(f"installing desktop entry -> {DESKTOP_DST}")
    _install_file(_render(_data_text("streamdock-n3-gui.desktop"), bin_dir), DESKTOP_DST)
    print("reloading udev")
    _reload_udev(vendor_id)
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
    parser.add_argument(
        "--device",
        choices=tuple(DEVICE_RULES),
        help="Device rule to install (normally selected interactively).",
    )
    args = parser.parse_args(argv)

    if os.geteuid() != 0:
        print("error: streamdock-n3-install must run as root (use sudo).", file=sys.stderr)
        return 1

    try:
        if args.uninstall:
            uninstall()
        else:
            try:
                device = select_device(args.device)
            except EOFError:
                print(
                    "error: choose a device with --device when running non-interactively.",
                    file=sys.stderr,
                )
                return 1
            install(_resolve_bin_dir(args.bin_dir), device)
    finally:
        # Runs on the failure path too: a half-finished install still imported
        # the package as root, so it still wrote the .pyc.
        _purge_root_owned_bytecode()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

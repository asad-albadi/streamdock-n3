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
    _install_file(_data_text("99-streamdock.rules"), UDEV_DST)
    print(f"installing systemd user unit -> {SERVICE_DST}")
    _install_file(_render(_data_text("streamdock-n3.service"), bin_dir), SERVICE_DST)
    print(f"installing desktop entry -> {DESKTOP_DST}")
    _install_file(_render(_data_text("streamdock-n3-gui.desktop"), bin_dir), DESKTOP_DST)
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

    try:
        if args.uninstall:
            uninstall()
        else:
            install(_resolve_bin_dir(args.bin_dir))
    finally:
        # Runs on the failure path too: a half-finished install still imported
        # the package as root, so it still wrote the .pyc.
        _purge_root_owned_bytecode()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import pytest

from streamdock_n3 import system_install


@pytest.mark.parametrize(
    "name",
    [
        "99-streamdock-mirabox.rules",
        "99-streamdock-hotspotekusb.rules",
        "streamdock-n3.service",
        "streamdock-n3-gui.desktop",
    ],
)
def test_packaged_data_files_are_readable(name):
    """_data_text is the install path; a lifetime bug here breaks sudo install."""
    assert system_install._data_text(name).strip()


def test_missing_data_file_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        system_install._data_text("does-not-exist.conf")


def test_render_substitutes_bin_dir(tmp_path):
    rendered = system_install._render(
        system_install._data_text("streamdock-n3.service"), tmp_path
    )
    assert f"ExecStart={tmp_path}/streamdock-n3" in rendered
    assert "@BIN@" not in rendered


def test_detect_connected_devices_by_vendor_id(tmp_path):
    mirabox = tmp_path / "1-1"
    hotspotek = tmp_path / "1-2"
    mirabox.mkdir()
    hotspotek.mkdir()
    (mirabox / "idVendor").write_text("6603\n", encoding="ascii")
    (hotspotek / "idVendor").write_text("5548\n", encoding="ascii")

    assert system_install.detect_connected_devices(tmp_path) == (
        "mirabox",
        "hotspotekusb",
    )


def test_select_device_defaults_to_detected_device(monkeypatch):
    monkeypatch.setattr(
        system_install, "detect_connected_devices", lambda: ("hotspotekusb",)
    )

    assert system_install.select_device(input_fn=lambda _prompt: "") == "hotspotekusb"


def test_select_device_allows_confirming_other_device(monkeypatch):
    monkeypatch.setattr(
        system_install, "detect_connected_devices", lambda: ("mirabox",)
    )

    assert system_install.select_device(input_fn=lambda _prompt: "2") == "hotspotekusb"


def test_install_writes_selected_rule_to_default_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(system_install, "UDEV_DST", tmp_path / "99-streamdock.rules")
    monkeypatch.setattr(system_install, "SERVICE_DST", tmp_path / "service")
    monkeypatch.setattr(system_install, "DESKTOP_DST", tmp_path / "desktop")
    monkeypatch.setattr(system_install, "_reload_udev", lambda _vendor_id=None: None)

    system_install.install(tmp_path, "hotspotekusb")

    assert system_install.UDEV_DST.name == "99-streamdock.rules"
    assert system_install.UDEV_DST.read_text(encoding="utf-8") == system_install._data_text(
        "99-streamdock-hotspotekusb.rules"
    )

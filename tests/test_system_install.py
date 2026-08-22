from __future__ import annotations

import pytest

from streamdock_n3 import system_install


@pytest.mark.parametrize(
    "name",
    ["99-streamdock.rules", "streamdock-n3.service", "streamdock-n3-gui.desktop"],
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

from __future__ import annotations

from pathlib import Path

from streamdock_n3 import paths


def test_dirs_honour_xdg_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert paths.config_file() == tmp_path / "cfg/streamdock-n3/config.json"
    assert paths.systemd_user_dir() == tmp_path / "cfg/systemd/user"
    assert paths.app_icon_dir() == tmp_path / "state/streamdock-n3/icons"
    assert paths.generated_key_dir() == tmp_path / "cache/streamdock-n3/keys"


def test_dirs_fall_back_to_home(monkeypatch):
    for var in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(var, raising=False)
    assert paths.systemd_user_dir() == Path.home() / ".config/systemd/user"
    assert paths.config_dir() == Path.home() / ".config/streamdock-n3"


def test_ensure_runtime_dirs_creates_everything(monkeypatch, tmp_path):
    for var in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        monkeypatch.setenv(var, str(tmp_path / var.lower()))
    paths.ensure_runtime_dirs()
    for d in (paths.config_dir(), paths.cache_dir(), paths.state_dir(),
              paths.app_icon_dir(), paths.generated_key_dir()):
        assert d.is_dir(), d

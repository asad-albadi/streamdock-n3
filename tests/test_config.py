from __future__ import annotations

import json

from streamdock_n3 import config as configmod


def test_action_map_returns_dict():
    assert configmod.action_map({"actions": {"a": "b"}}) == {"a": "b"}
    assert configmod.action_map({}) == {}
    assert configmod.action_map({"actions": "nonsense"}) == {}


def test_ensure_config_creates_default(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr("streamdock_n3.paths.config_file", lambda: cfg_path)
    configmod.ensure_config()
    assert cfg_path.is_file()
    data = json.loads(cfg_path.read_text())
    assert "brightness" in data
    assert "keys" in data
    assert "actions" in data


def test_load_then_save_roundtrip(tmp_path):
    cfg = {"brightness": 42, "keys": {"1": {"label": "A"}}, "actions": {"button.1.press": "echo"}}
    target = tmp_path / "x.json"
    configmod.save(cfg, target)
    assert configmod.load(target) == cfg


def test_load_rejects_non_object(tmp_path):
    target = tmp_path / "bad.json"
    target.write_text("[]")
    import pytest
    with pytest.raises(ValueError):
        configmod.load(target)

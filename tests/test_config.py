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


def test_normalize_replaces_missing_keys_object():
    cfg = configmod.normalize({})
    assert cfg["keys"] == {}
    assert cfg["actions"] == {}


def test_normalize_coerces_non_dict_entries():
    cfg = configmod.normalize({"keys": {"1": "Term", "2": {"label": "Web"}}})
    assert cfg["keys"] == {"1": {}, "2": {"label": "Web"}}


def test_normalize_coerces_non_dict_containers():
    cfg = configmod.normalize({"keys": "nonsense", "actions": []})
    assert cfg["keys"] == {}
    assert cfg["actions"] == {}


def test_normalize_stringifies_integer_key_ids():
    cfg = configmod.normalize({"keys": {1: {"label": "A"}}})
    assert cfg["keys"] == {"1": {"label": "A"}}


def test_normalize_preserves_valid_config():
    original = {"brightness": 42, "keys": {"1": {"label": "A"}}, "actions": {"x": "y"}}
    assert configmod.normalize(dict(original)) == original

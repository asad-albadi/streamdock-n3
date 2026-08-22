from __future__ import annotations

from streamdock_n3.daemon import wants_evdev_grab


def test_grab_when_evdev_actions_present():
    assert wants_evdev_grab({"evdev.KEY_MUTE.press": "x"}, {}) is True


def test_no_grab_without_evdev_actions():
    assert wants_evdev_grab({"button.1.press": "x"}, {}) is False
    assert wants_evdev_grab({}, {}) is False


def test_grab_opt_out_via_config():
    actions = {"evdev.KEY_MUTE.press": "x"}
    assert wants_evdev_grab(actions, {"grab_evdev": False}) is False
    assert wants_evdev_grab(actions, {"grab_evdev": True}) is True

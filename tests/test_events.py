from __future__ import annotations

from types import SimpleNamespace

from streamdock_n3._vendor.StreamDock.InputTypes import (
    ButtonKey,
    Direction,
    EventType,
    InputEvent,
    KnobId,
)
from streamdock_n3.events import describe_event, evdev_event_key, event_key


def test_evdev_event_key_press_release_repeat():
    assert evdev_event_key("KEY_VOLUMEUP", 1) == "evdev.KEY_VOLUMEUP.press"
    assert evdev_event_key("KEY_VOLUMEUP", 0) == "evdev.KEY_VOLUMEUP.release"
    assert evdev_event_key("KEY_VOLUMEUP", 2) == "evdev.KEY_VOLUMEUP.repeat"


def test_event_key_button_press():
    ev = InputEvent(event_type=EventType.BUTTON, key=ButtonKey.KEY_1, state=1)
    assert event_key(ev) == "button.1.press"


def test_event_key_button_release():
    ev = InputEvent(event_type=EventType.BUTTON, key=ButtonKey.KEY_7, state=0)
    assert event_key(ev) == "button.7.release"


def test_event_key_knob_rotate():
    ev = InputEvent(
        event_type=EventType.KNOB_ROTATE,
        knob_id=KnobId.KNOB_2,
        direction=Direction.LEFT,
    )
    assert event_key(ev) == "knob.2.left"


def test_event_key_knob_press():
    ev = InputEvent(event_type=EventType.KNOB_PRESS, knob_id=KnobId.KNOB_3, state=1)
    assert event_key(ev) == "knob.3.press"


def test_describe_event_button():
    ev = InputEvent(event_type=EventType.BUTTON, key=ButtonKey.KEY_1, state=1)
    assert describe_event(ev) == "lcd key 1 pressed"


def test_describe_event_unknown_returns_string():
    ev = SimpleNamespace(event_type="bogus")
    assert isinstance(describe_event(ev), str)

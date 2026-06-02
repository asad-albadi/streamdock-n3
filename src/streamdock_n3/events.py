"""Event name mapping and human-readable descriptions."""

from __future__ import annotations

from streamdock_n3._vendor.StreamDock.InputTypes import EventType  # noqa: E402

BUTTON_NAMES: dict[int, str] = {
    1: "lcd key 1",
    2: "lcd key 2",
    3: "lcd key 3",
    4: "lcd key 4",
    5: "lcd key 5",
    6: "lcd key 6",
    7: "round button 1",
    8: "round button 2",
    9: "round button 3",
}

KNOB_NAMES: dict[str, str] = {
    "knob_1": "small knob 1",
    "knob_2": "small knob 2",
    "knob_3": "large knob",
}


def event_key(event) -> str | None:
    if event.event_type == EventType.BUTTON:
        state = "press" if event.state else "release"
        return f"button.{event.key.value}.{state}"
    if event.event_type == EventType.KNOB_PRESS:
        state = "press" if event.state else "release"
        knob = event.knob_id.value.replace("knob_", "")
        return f"knob.{knob}.{state}"
    if event.event_type == EventType.KNOB_ROTATE:
        knob = event.knob_id.value.replace("knob_", "")
        return f"knob.{knob}.{event.direction.value}"
    return None


def evdev_event_key(keycode: str, value: int) -> str:
    state = "press" if value == 1 else "release" if value == 0 else "repeat"
    return f"evdev.{keycode}.{state}"


def describe_event(event) -> str:
    if event.event_type == EventType.BUTTON:
        state = "pressed" if event.state else "released"
        name = BUTTON_NAMES.get(event.key.value, f"button {event.key.value}")
        return f"{name} {state}"
    if event.event_type == EventType.KNOB_PRESS:
        state = "pressed" if event.state else "released"
        name = KNOB_NAMES.get(event.knob_id.value, event.knob_id.value)
        return f"{name} {state}"
    if event.event_type == EventType.KNOB_ROTATE:
        name = KNOB_NAMES.get(event.knob_id.value, event.knob_id.value)
        return f"{name} rotated {event.direction.value}"
    return "unknown event"

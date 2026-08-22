from __future__ import annotations

from tests.gui_source import load_gui_function

render_action = load_gui_function("render_action")


def test_plain_string_is_unchanged():
    assert render_action("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle") == (
        "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"
    )


def test_list_joins_with_semicolon_not_and():
    # "&&" would make the second command depend on the first succeeding;
    # run_actions launches them independently.
    assert render_action(["cmd a", "cmd b"]) == "cmd a; cmd b"


def test_dict_uses_command_field():
    assert render_action({"command": "obs"}) == "obs"
    assert render_action({"nothing": "here"}) == ""


def test_list_of_dicts_does_not_raise():
    # This shape is legal for run_actions; " && ".join used to raise TypeError
    # here, which happened during window construction and blocked GUI startup.
    assert render_action([{"command": "x"}, "y"]) == "x; y"


def test_missing_and_odd_values_degrade():
    assert render_action("") == ""
    assert render_action(None) == ""
    assert render_action(42) == "42"

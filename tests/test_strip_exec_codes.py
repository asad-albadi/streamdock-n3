from __future__ import annotations

from tests.gui_source import load_gui_function

strip_exec_codes = load_gui_function("strip_exec_codes")


def test_strips_field_codes():
    assert strip_exec_codes("foo %U") == "foo"
    assert strip_exec_codes("foo %f bar %u") == "foo bar"


def test_preserves_literal_percent():
    assert strip_exec_codes("printf 100%%") == "printf 100%"


def test_collapses_whitespace():
    assert strip_exec_codes("a   b    c") == "a b c"

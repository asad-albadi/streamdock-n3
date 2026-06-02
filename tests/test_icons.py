from __future__ import annotations

from streamdock_n3.icons import make_icon, parse_color


def test_parse_color_six_digit_hex():
    assert parse_color("#1c63b8", (0, 0, 0)) == (28, 99, 184)


def test_parse_color_without_hash():
    assert parse_color("1c63b8", (0, 0, 0)) == (28, 99, 184)


def test_parse_color_invalid_returns_fallback():
    assert parse_color("zzzzzz", (1, 2, 3)) == (1, 2, 3)
    assert parse_color("#123", (1, 2, 3)) == (1, 2, 3)
    assert parse_color(None, (1, 2, 3)) == (1, 2, 3)
    assert parse_color(42, (1, 2, 3)) == (1, 2, 3)


def test_make_icon_writes_file(tmp_path):
    out = tmp_path / "k.jpg"
    make_icon("Hi", (10, 20, 30), out)
    assert out.is_file()
    assert out.stat().st_size > 0

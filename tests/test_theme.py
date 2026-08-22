from __future__ import annotations

import re

import pytest

from streamdock_n3 import theme

# ----- the invariant GTK will not check for us -----------------------------


def test_every_referenced_colour_is_defined():
    """GTK does not report an undefined @colour as a parsing error.

    It resolves colours lazily and silently, so a name no theme defines yields a
    broken colour with no warning anywhere. The fallback provider therefore has
    to define everything the stylesheets reference, and only a test can prove it.
    """
    fallback = theme.build_fallback_css(theme.fallback_palette(dark=True))
    for name, css in (("app", theme.build_app_css()), ("fallback", fallback)):
        missing = theme.referenced_colors(css) - set(theme.COLOR_NAMES)
        assert not missing, f"{name} CSS references undefined colours: {sorted(missing)}"


def test_fallback_css_defines_every_declared_name():
    css = theme.build_fallback_css(theme.fallback_palette(dark=False))
    defined = set(re.findall(r"@define-color\s+([A-Za-z0-9_]+)", css))
    assert defined == set(theme.COLOR_NAMES)


def test_app_css_hardcodes_no_colours_or_fonts():
    """The two things that made the GUI ignore the desktop."""
    css = theme.build_app_css()
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", css), "app CSS still hardcodes a colour"
    assert "font-family" not in css, "app CSS still hardcodes a font family"
    assert "pt" not in css, "app CSS still uses absolute font sizes"


def test_app_css_does_not_restyle_theme_owned_widgets():
    """Styling these is what overrode the system theme in the first place."""
    css = theme.build_app_css()
    for selector in ("window", "headerbar", "notebook", "entry", "button", "scale", "frame"):
        assert not re.search(rf"(?m)^\s*{selector}\b", css), f"app CSS restyles {selector}"


# ----- palettes -----------------------------------------------------------


@pytest.mark.parametrize("dark", [True, False])
def test_fallback_palette_is_complete(dark):
    palette = theme.fallback_palette(dark=dark)
    assert set(palette) == set(theme.COLOR_NAMES)
    assert all(re.fullmatch(r"#[0-9a-fA-F]{6}", v) for v in palette.values())


def test_light_and_dark_actually_differ():
    assert theme.fallback_palette(dark=True) != theme.fallback_palette(dark=False)
    assert theme.fallback_palette(dark=True)["window_bg_color"] != (
        theme.fallback_palette(dark=False)["window_bg_color"]
    )


def test_overrides_applied_and_validated():
    palette = theme.fallback_palette(
        dark=True,
        overrides={
            "window_bg_color": "#123456",   # valid, known
            "accent_color": "not-a-colour",  # invalid value, ignored
            "made_up_name": "#ffffff",       # unknown name, ignored
        },
    )
    assert palette["window_bg_color"] == "#123456"
    assert palette["accent_color"] == theme.DARK_FALLBACK["accent_color"]
    assert "made_up_name" not in palette


# ----- Omarchy compatibility ---------------------------------------------


def test_parse_omarchy_palette_maps_semantic_names():
    got = theme.parse_omarchy_palette(
        'background = "#1e1e2e"\n'
        "foreground = '#cdd6f4'  # trailing comment\n"
        "accent = #89b4fa\n"
        "color2 = #a6e3a1\n"
    )
    assert got["window_bg_color"] == "#1e1e2e"
    assert got["window_fg_color"] == "#cdd6f4"
    assert got["accent_color"] == "#89b4fa"
    assert got["success_color"] == "#a6e3a1"


def test_parse_omarchy_palette_ignores_junk():
    got = theme.parse_omarchy_palette(
        "# background = #ffffff\n"       # commented out
        "background = not-a-colour\n"    # unparseable
        "unknown_key = #ffffff\n"        # not mapped
        "no equals sign here\n"
        "\n"
    )
    assert got == {}


def test_parse_omarchy_palette_accepts_shorthand():
    assert theme.parse_omarchy_palette("background = #abc")["window_bg_color"] == "#abc"


def test_omarchy_palette_feeds_through_to_css():
    """An Omarchy user's colours must survive into the generated stylesheet."""
    overrides = theme.parse_omarchy_palette('background = "#1e1e2e"')
    css = theme.build_fallback_css(theme.fallback_palette(dark=True, overrides=overrides))
    assert "@define-color window_bg_color #1e1e2e;" in css


# ----- mode selection -----------------------------------------------------


def test_theme_mode_defaults_to_system():
    assert theme.theme_mode({}) == "system"


@pytest.mark.parametrize("mode", theme.THEME_MODES)
def test_theme_mode_accepts_each_valid_mode(mode):
    assert theme.theme_mode({"theme": mode}) == mode


def test_theme_mode_is_case_and_space_tolerant():
    assert theme.theme_mode({"theme": "  Omarchy "}) == "omarchy"


@pytest.mark.parametrize("bad", ["nonsense", "", 42, None, [], {"a": 1}])
def test_theme_mode_falls_back_to_system_on_junk(bad):
    """A typo must not silently resurrect the old hardcoded palette."""
    assert theme.theme_mode({"theme": bad}) == "system"


def test_app_css_carries_explicit_overrides_above_the_theme():
    """Omarchy mode only works if its definitions outrank the GTK theme."""
    css = theme.build_app_css({"window_bg_color": "#1e1e2e", "made_up": "#fff"})
    assert "@define-color window_bg_color #1e1e2e;" in css
    assert "made_up" not in css, "unknown colour names must not be emitted"
    # The semantic classes must still be present alongside the overrides.
    assert ".section-title" in css


def test_app_css_without_overrides_is_still_literal_free():
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", theme.build_app_css(None))

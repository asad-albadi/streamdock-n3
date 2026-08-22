"""Styling that follows the desktop theme instead of overriding it.

The GUI used to paint every colour itself from a hardcoded palette, so on any
machine without Omarchy's ``colors.toml`` it ignored the desktop's light/dark
preference, accent colour and font entirely. Colours now come from the platform,
using GTK's own cascade:

===================  ==========================================================
priority             provider
===================  ==========================================================
1    ``FALLBACK``    our ``@define-color`` defaults (this module)
200  ``THEME``       libadwaita / Adwaita / the active GTK theme
600  ``APPLICATION`` only the semantic classes no theme defines (this module)
800  ``USER``        ``~/.config/gtk-4.0/gtk.css``
===================  ==========================================================

Defining every name at priority 1 is what makes this safe everywhere: GTK
resolves colours lazily and does *not* report an undefined name as a parsing
error, so referencing one that no theme happens to define yields a silently
broken colour. With defaults underneath, a theme that defines the name wins and
one that doesn't still renders correctly.

Widgets the theme already knows how to draw -- window, headerbar, notebook,
entry, button, scale -- are deliberately left alone, which is the whole point:
those are the ones that were previously overridden.

This module is pure: it does not import ``gi``, so it is unit-testable in CI,
where GTK is not installed.
"""

from __future__ import annotations

import re
from typing import Any

# Names referenced by the generated CSS. Every one must appear in the fallback
# palettes below; tests assert that, because GTK will not.
COLOR_NAMES: tuple[str, ...] = (
    "window_bg_color",
    "window_fg_color",
    "view_bg_color",
    "view_fg_color",
    "card_bg_color",
    "card_fg_color",
    "headerbar_bg_color",
    "headerbar_fg_color",
    "accent_color",
    "accent_bg_color",
    "accent_fg_color",
    "success_color",
    "warning_color",
    "error_color",
)

# libadwaita's documented light/dark values, used only when neither the theme
# nor the user's gtk.css defines a name (a bare GTK4 install without
# libadwaita, for instance).
DARK_FALLBACK: dict[str, str] = {
    "window_bg_color": "#242424",
    "window_fg_color": "#ffffff",
    "view_bg_color": "#1d1d1d",
    "view_fg_color": "#ffffff",
    "card_bg_color": "#303030",
    "card_fg_color": "#ffffff",
    "headerbar_bg_color": "#303030",
    "headerbar_fg_color": "#ffffff",
    "accent_color": "#78aeed",
    "accent_bg_color": "#3584e4",
    "accent_fg_color": "#ffffff",
    "success_color": "#8ff0a4",
    "warning_color": "#f8e45c",
    "error_color": "#ff7b63",
}

LIGHT_FALLBACK: dict[str, str] = {
    "window_bg_color": "#fafafa",
    "window_fg_color": "#323232",
    "view_bg_color": "#ffffff",
    "view_fg_color": "#323232",
    "card_bg_color": "#ffffff",
    "card_fg_color": "#323232",
    "headerbar_bg_color": "#ebebeb",
    "headerbar_fg_color": "#323232",
    "accent_color": "#1c71d8",
    "accent_bg_color": "#3584e4",
    "accent_fg_color": "#ffffff",
    "success_color": "#2ec27e",
    "warning_color": "#e5a50a",
    "error_color": "#c01c28",
}

# Omarchy publishes a terminal-style palette. Map it onto the semantic names so
# an Omarchy user opting in with "theme": "omarchy" gets what they had before.
OMARCHY_MAP: dict[str, tuple[str, ...]] = {
    "background": ("window_bg_color", "view_bg_color", "headerbar_bg_color"),
    "foreground": ("window_fg_color", "view_fg_color", "headerbar_fg_color", "card_fg_color"),
    "accent": ("accent_color", "accent_bg_color"),
    "color0": ("card_bg_color",),
    "color1": ("error_color",),
    "color2": ("success_color",),
    "color3": ("warning_color",),
}

THEME_MODES = ("system", "omarchy", "light", "dark")


def theme_mode(config: dict[str, Any]) -> str:
    """Read the ``theme`` config key, tolerating anything unexpected.

    Defaults to "system" so a config written before this option existed -- and
    one with a typo in it -- follows the desktop rather than silently falling
    back to the old hardcoded palette.
    """
    value = config.get("theme", "system")
    if isinstance(value, str) and value.strip().lower() in THEME_MODES:
        return value.strip().lower()
    return "system"


def _is_hex_colour(value: str) -> bool:
    return bool(re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value))


def parse_omarchy_palette(text: str) -> dict[str, str]:
    """Extract semantic colours from an Omarchy ``colors.toml``.

    Deliberately a line scanner rather than a TOML parse: the file is a flat
    ``key = "#rrggbb"`` list, tolerating junk matters more than strictness, and
    this keeps the module dependency-free and importable without GTK.
    """
    palette: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        if key not in OMARCHY_MAP:
            continue
        # Pull the literal out by pattern rather than by stripping quotes: that
        # way surrounding quotes, whitespace and a trailing comment all fall
        # away without a separate rule for each.
        match = re.search(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", value)
        if match is None:
            continue
        for name in OMARCHY_MAP[key]:
            palette.setdefault(name, match.group(0))
    return palette


def fallback_palette(*, dark: bool, overrides: dict[str, str] | None = None) -> dict[str, str]:
    """The palette installed at priority 1, with optional overrides on top."""
    palette = dict(DARK_FALLBACK if dark else LIGHT_FALLBACK)
    for name, value in (overrides or {}).items():
        if name in palette and _is_hex_colour(value):
            palette[name] = value
    return palette


def build_fallback_css(palette: dict[str, str]) -> str:
    """Colour definitions, plus styling for classes a theme may not provide.

    Installed at ``FALLBACK`` priority so every real theme overrides it. The
    ``.card`` / ``.suggested-action`` / ``.linked`` rules exist because those are
    platform style classes: when libadwaita or Adwaita is present it styles them
    far better than we would, and when nothing does they would otherwise render
    as flat unstyled boxes.
    """
    defines = "\n".join(f"@define-color {name} {palette[name]};" for name in COLOR_NAMES)
    return f"""{defines}

.card {{
    background: @card_bg_color;
    color: @card_fg_color;
    border-radius: 12px;
    padding: 12px 14px;
}}
button.suggested-action {{
    background: @accent_bg_color;
    color: @accent_fg_color;
}}
box.linked > button:not(:first-child) {{
    border-left-width: 0;
}}
"""


def build_app_css(overrides: dict[str, str] | None = None) -> str:
    """Only the classes this app invents; no literal colours, no font.

    Anything a GTK theme already draws is absent on purpose. Fonts especially:
    hardcoding a family and point size was why the GUI ignored the desktop font.

    ``overrides`` is for an explicit opt-out such as ``"theme": "omarchy"``. Those
    definitions have to live here, at APPLICATION priority, rather than in the
    fallback sheet: the fallback sits *below* libadwaita and the GTK theme, so
    anything placed there would simply lose to them. They still sit below the
    user's own gtk.css, which stays the last word.
    """
    prefix = ""
    if overrides:
        prefix = "\n".join(
            f"@define-color {name} {value};"
            for name, value in sorted(overrides.items())
            if name in COLOR_NAMES
        ) + "\n"
    return prefix + """
.section-title {
    color: @accent_color;
    font-weight: bold;
    margin: 12px 4px 4px 4px;
}
.dim {
    color: alpha(@window_fg_color, 0.6);
    font-size: 0.9em;
}
.status-dot {
    font-size: 1.3em;
}
.status-ok {
    color: @success_color;
    font-weight: bold;
}
.status-bad {
    color: @error_color;
    font-weight: bold;
}
label.key-pill {
    background: alpha(@window_fg_color, 0.1);
    border-radius: 6px;
    padding: 2px 8px;
    font-weight: bold;
}
label.toast {
    background: @card_bg_color;
    color: @card_fg_color;
    border: 1px solid @accent_color;
    border-radius: 8px;
    padding: 8px 12px;
}
"""


def referenced_colors(css: str) -> set[str]:
    """Every ``@name`` a stylesheet refers to, excluding its own definitions.

    Used by the tests to prove no rule can reference a colour the fallback does
    not define -- the failure GTK refuses to report.
    """
    defined = set(re.findall(r"@define-color\s+([A-Za-z0-9_]+)", css))
    # Strip the declarations before scanning for references: "@define-color" is
    # itself an @-token, and the reference pattern stops at the hyphen, so it
    # would otherwise report a phantom colour named "define".
    body = re.sub(r"@define-color\s+[A-Za-z0-9_]+[^;]*;", "", css)
    used = set(re.findall(r"@([A-Za-z0-9_]+)", body))
    return used - defined

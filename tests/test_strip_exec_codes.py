from __future__ import annotations

# The GUI module imports `gi`; only import the helper we need without requiring GTK.
# strip_exec_codes is a pure-string utility so we re-import the implementation here.
from pathlib import Path


def _load_strip_exec_codes():
    """Load strip_exec_codes from gui.py without triggering the gi import."""
    src = Path(__file__).resolve().parents[1] / "src/streamdock_n3/gui.py"
    text = src.read_text(encoding="utf-8")

    # Crude but effective: locate the function definition and exec it in a clean ns.
    marker = "def strip_exec_codes("
    start = text.index(marker)
    # Find the next top-level def to bound the function.
    end = text.index("\ndef ", start + len(marker))
    snippet = text[start:end]
    ns: dict = {}
    exec(snippet, ns)
    return ns["strip_exec_codes"]


strip_exec_codes = _load_strip_exec_codes()


def test_strips_field_codes():
    assert strip_exec_codes("foo %U") == "foo"
    assert strip_exec_codes("foo %f bar %u") == "foo bar"


def test_preserves_literal_percent():
    assert strip_exec_codes("printf 100%%") == "printf 100%"


def test_collapses_whitespace():
    assert strip_exec_codes("a   b    c") == "a b c"

#!/usr/bin/env python3
"""Omarchy-themed GTK4 GUI for streamdock-n3-linux."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

LOG_PATH = Path("/tmp/streamdock-n3-gui.log")
logging.basicConfig(
    filename=str(LOG_PATH),
    filemode="w",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("streamdock-gui")


def _excepthook(exc_type, exc, tb):
    log.error("UNCAUGHT: %s", "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _excepthook

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gio, Gtk  # noqa: E402


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "streamdock-n3-linux.config.json"
SERVICE = "streamdock-n3-linux.service"
SERVICE_SRC = ROOT / SERVICE
SERVICE_DST_DIR = Path.home() / ".config/systemd/user"
SERVICE_DST = SERVICE_DST_DIR / SERVICE
APP_ID = "om.vodafone.streamdock.N3"
VID = "6603"
PID = "1003"

OMARCHY_THEME = Path.home() / ".config/omarchy/current/theme/colors.toml"

LCD_KEYS = [1, 2, 3, 4, 5, 6]
ROUND_BUTTONS = [7, 8, 9]
KNOBS = [1, 2, 3]
KNOB_LABELS = {1: "Small knob 1", 2: "Small knob 2", 3: "Large knob"}
ROUND_LABELS = {7: "Round button 1", 8: "Round button 2", 9: "Round button 3"}

ICON_CACHE_DIR = Path.home() / ".cache/streamdock-n3-linux/icons"
ICON_RENDER_SIZE = 144  # px, captured PNG side

DEFAULT_PALETTE = {
    "background": "#1e1e2e",
    "foreground": "#cdd6f4",
    "accent": "#89b4fa",
    "color0": "#45475a",
    "color1": "#f38ba8",
    "color2": "#a6e3a1",
    "color8": "#585b70",
}


# ----- config IO ----------------------------------------------------------


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_config(data: dict[str, Any]) -> None:
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, CONFIG_PATH)


# ----- system probes ------------------------------------------------------


def systemctl(action: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["systemctl", "--user", action, SERVICE],
            capture_output=True, text=True, timeout=10,
        )
        out = (r.stdout + r.stderr).strip()
        log.info("systemctl %s -> rc=%s out=%r", action, r.returncode, out)
        return r.returncode == 0, out or action
    except Exception as exc:  # noqa: BLE001
        log.exception("systemctl %s failed", action)
        return False, str(exc)


def service_active() -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", SERVICE],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() == "active"
    except Exception:  # noqa: BLE001
        log.exception("service_active failed")
        return False


def device_present() -> bool:
    """Scan /sys/bus/usb/devices for VID:PID — no lsusb dependency."""
    try:
        for dev in Path("/sys/bus/usb/devices").glob("*"):
            vid_f = dev / "idVendor"
            pid_f = dev / "idProduct"
            if vid_f.exists() and pid_f.exists():
                if (
                    vid_f.read_text().strip().lower() == VID.lower()
                    and pid_f.read_text().strip().lower() == PID.lower()
                ):
                    return True
        return False
    except Exception:  # noqa: BLE001
        log.exception("device_present failed")
        return False


def service_installed() -> bool:
    return SERVICE_DST.exists()


def list_installed_apps() -> list[Gio.AppInfo]:
    apps = [a for a in Gio.AppInfo.get_all() if a.should_show()]
    apps.sort(key=lambda a: (a.get_display_name() or "").lower())
    return apps


def strip_exec_codes(cmd: str) -> str:
    """Remove freedesktop Exec field codes (%f, %U, etc.)."""
    out = []
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if ch == "%" and i + 1 < len(cmd):
            nxt = cmd[i + 1]
            if nxt == "%":
                out.append("%")
            # any other %x is dropped silently
            i += 2
            continue
        out.append(ch)
        i += 1
    return " ".join("".join(out).split())  # collapse whitespace


def icon_path_for_app(app: Gio.AppInfo, size: int = ICON_RENDER_SIZE) -> str | None:
    """Return a resolvable file path for the app's icon, rasterising SVG to PNG."""
    icon = app.get_icon()
    if icon is None:
        return None

    display = Gdk.Display.get_default()
    theme = Gtk.IconTheme.get_for_display(display) if display else None

    source_path: str | None = None
    try:
        if isinstance(icon, Gio.FileIcon):
            f = icon.get_file()
            if f is not None:
                source_path = f.get_path()
        elif isinstance(icon, Gio.ThemedIcon) and theme is not None:
            for name in icon.get_names():
                if theme.has_icon(name):
                    paintable = theme.lookup_icon(
                        name, None, size, 1, Gtk.TextDirection.NONE, 0
                    )
                    f = paintable.get_file()
                    if f is not None:
                        source_path = f.get_path()
                        break
    except Exception:  # noqa: BLE001
        log.exception("icon lookup failed")
        return None

    if not source_path or not Path(source_path).is_file():
        return None

    try:
        from gi.repository import GdkPixbuf
        ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        app_id = app.get_id() or app.get_display_name() or "app"
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in app_id)
        out_path = ICON_CACHE_DIR / f"{safe}.png"
        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(source_path, size, size)
        pb.savev(str(out_path), "png", [], [])
        return str(out_path)
    except Exception:  # noqa: BLE001
        log.exception("icon rasterize failed for %s", source_path)
        # last resort: hand back original even if SVG — PIL may not load it
        return source_path


def install_service() -> tuple[bool, str]:
    try:
        SERVICE_DST_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SERVICE_SRC, SERVICE_DST)
        r = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True, text=True, timeout=10,
        )
        log.info("install_service: copied + daemon-reload rc=%s", r.returncode)
        return r.returncode == 0, (r.stdout + r.stderr).strip() or "installed"
    except Exception as exc:  # noqa: BLE001
        log.exception("install_service failed")
        return False, str(exc)


# ----- theme palette ------------------------------------------------------


def parse_palette(path: Path) -> dict[str, str]:
    palette = dict(DEFAULT_PALETTE)
    if not path.exists():
        return palette
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if v.startswith("#") and len(v) in (4, 7):
                palette[k] = v
    except Exception:  # noqa: BLE001
        pass
    return palette


def build_css(p: dict[str, str]) -> str:
    bg = p.get("background", "#1e1e2e")
    fg = p.get("foreground", "#cdd6f4")
    accent = p.get("accent", "#89b4fa")
    surface = p.get("color0", "#45475a")
    surface_hi = p.get("color8", "#585b70")
    err = p.get("color1", "#f38ba8")
    ok = p.get("color2", "#a6e3a1")
    return f"""
window, .background {{
    background-color: {bg};
    color: {fg};
    font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace;
    font-size: 11pt;
}}
headerbar {{
    background: {bg};
    color: {fg};
    border-bottom: 1px solid {surface};
    padding: 4px 8px;
    min-height: 36px;
}}
headerbar label.title {{
    color: {fg};
    font-weight: bold;
}}
notebook header {{
    background: {bg};
    border-bottom: 1px solid {surface};
}}
notebook header tab {{
    background: transparent;
    color: {fg};
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
}}
notebook header tab:checked {{
    color: {accent};
    border-bottom: 2px solid {accent};
}}
notebook header tab:hover {{
    color: {accent};
}}
.card {{
    background: {surface};
    border-radius: 8px;
    padding: 12px 14px;
    margin: 6px 0;
}}
.section-title {{
    color: {accent};
    font-weight: bold;
    margin: 12px 4px 4px 4px;
}}
.dim {{
    color: {surface_hi};
    font-size: 9pt;
}}
.status-ok {{ color: {ok}; font-weight: bold; }}
.status-bad {{ color: {err}; font-weight: bold; }}
.status-dot {{ font-size: 14pt; }}
entry, spinbutton {{
    background: {bg};
    color: {fg};
    border: 1px solid {surface_hi};
    border-radius: 6px;
    padding: 6px 8px;
    caret-color: {accent};
}}
entry:focus, spinbutton:focus {{
    border-color: {accent};
    outline: none;
}}
button {{
    background: {surface};
    color: {fg};
    border: 1px solid {surface_hi};
    border-radius: 6px;
    padding: 6px 12px;
}}
button:hover {{
    background: {surface_hi};
}}
button.accent {{
    background: {accent};
    color: {bg};
    border: 1px solid {accent};
    font-weight: bold;
}}
button.accent:hover {{
    background: shade({accent}, 1.1);
}}
button:disabled {{
    opacity: 0.45;
}}
scale trough {{
    background: {surface};
    border-radius: 4px;
    min-height: 6px;
}}
scale highlight {{
    background: {accent};
    border-radius: 4px;
}}
scale slider {{
    background: {accent};
    border: none;
    border-radius: 50%;
}}
scrolledwindow {{ background: {bg}; }}
toast {{
    background: {surface};
    color: {fg};
    border: 1px solid {accent};
    border-radius: 6px;
    padding: 8px 12px;
}}
label.key-pill {{
    background: {surface};
    color: {fg};
    border-radius: 4px;
    padding: 2px 8px;
    font-weight: bold;
}}
box.linked > button {{
    border-radius: 0;
    margin: 0;
    border-right-width: 0;
}}
box.linked > button:first-child {{
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
}}
box.linked > button:last-child {{
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    border-right-width: 1px;
}}
box.linked > button:checked {{
    background: {accent};
    color: {bg};
    border-color: {accent};
}}
frame {{
    background: {bg};
    border: 1px solid {surface_hi};
    border-radius: 6px;
}}
"""


# ----- helpers ------------------------------------------------------------


def parse_hex(color: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(color if color.startswith("#") else f"#{color}")
    return rgba


def rgba_to_hex(rgba: Gdk.RGBA) -> str:
    return f"#{int(round(rgba.red*255)):02x}{int(round(rgba.green*255)):02x}{int(round(rgba.blue*255)):02x}"


def section_label(text: str) -> Gtk.Label:
    lbl = Gtk.Label(label=text, xalign=0)
    lbl.add_css_class("section-title")
    return lbl


def dim_label(text: str) -> Gtk.Label:
    lbl = Gtk.Label(label=text, xalign=0)
    lbl.add_css_class("dim")
    lbl.set_wrap(True)
    return lbl


def field_row(label_text: str, widget: Gtk.Widget) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    box.set_margin_top(4)
    box.set_margin_bottom(4)
    lbl = Gtk.Label(label=label_text, xalign=0)
    lbl.set_size_request(110, -1)
    box.append(lbl)
    if isinstance(widget, (Gtk.Entry, Gtk.Scale)):
        widget.set_hexpand(True)
    box.append(widget)
    return box


def card(child: Gtk.Widget) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.add_css_class("card")
    box.append(child)
    return box


class AppPickerDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window, on_pick) -> None:
        super().__init__(title="Choose application", transient_for=parent, modal=True)
        self.set_default_size(480, 560)
        self._on_pick = on_pick

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        self.set_child(outer)

        search = Gtk.SearchEntry()
        search.set_placeholder_text("Search applications")
        search.connect("search-changed", self._on_search)
        outer.append(search)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", self._on_row_activated)
        scroll.set_child(self.listbox)
        outer.append(scroll)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.close())
        self.select_btn = Gtk.Button(label="Select")
        self.select_btn.add_css_class("accent")
        self.select_btn.connect("clicked", self._on_select)
        btns.append(cancel)
        btns.append(self.select_btn)
        outer.append(btns)

        self._rows: list[tuple[Gtk.ListBoxRow, Gio.AppInfo, str]] = []
        for app in list_installed_apps():
            row = self._build_row(app)
            self.listbox.append(row)
            haystack = ((app.get_display_name() or "") + " "
                        + (app.get_commandline() or "")).lower()
            self._rows.append((row, app, haystack))

    def _build_row(self, app: Gio.AppInfo) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(6)
        box.set_margin_end(6)

        img = Gtk.Image()
        img.set_pixel_size(28)
        icon = app.get_icon()
        if icon is not None:
            img.set_from_gicon(icon)
        else:
            img.set_from_icon_name("application-x-executable")
        box.append(img)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        text_box.set_hexpand(True)
        name = Gtk.Label(label=app.get_display_name() or "(unnamed)", xalign=0)
        cmd = Gtk.Label(label=app.get_commandline() or "", xalign=0)
        cmd.add_css_class("dim")
        cmd.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        text_box.append(name)
        text_box.append(cmd)
        box.append(text_box)

        row.set_child(box)
        row._app = app  # type: ignore[attr-defined]
        return row

    def _on_search(self, entry: Gtk.SearchEntry) -> None:
        q = entry.get_text().lower().strip()
        for row, _app, haystack in self._rows:
            row.set_visible(not q or q in haystack)

    def _on_row_activated(self, _lb, row) -> None:
        self._confirm(row)

    def _on_select(self, _btn) -> None:
        self._confirm(self.listbox.get_selected_row())

    def _confirm(self, row) -> None:
        log.info("AppPicker confirm row=%s", row)
        if row is None:
            return
        app = getattr(row, "_app", None)
        if app is None:
            log.warning("row has no _app attr")
            self.close()
            return
        try:
            self._on_pick(app)
        except Exception:  # noqa: BLE001
            log.exception("on_pick callback failed")
        finally:
            self.close()


# ----- main window --------------------------------------------------------


class StreamDockWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="Stream Dock N3")
        self.set_default_size(680, 780)
        self.config: dict[str, Any] = load_config()
        self._dirty = False
        self._toasts: list[Gtk.Revealer] = []

        # header
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        title = Gtk.Label(label="Stream Dock N3")
        title.add_css_class("title")
        header.set_title_widget(title)

        self.reload_btn = Gtk.Button(label="Reload")
        self.reload_btn.set_tooltip_text("Reload config from disk")
        self.reload_btn.connect("clicked", self.on_reload)
        header.pack_start(self.reload_btn)

        self.save_btn = Gtk.Button(label="Save")
        self.save_btn.add_css_class("accent")
        self.save_btn.set_sensitive(False)
        self.save_btn.connect("clicked", self.on_save)
        header.pack_end(self.save_btn)
        self.set_titlebar(header)

        # overlay holds toasts on top
        overlay = Gtk.Overlay()
        self.overlay = overlay
        self.set_child(overlay)

        notebook = Gtk.Notebook()
        notebook.set_margin_top(8)
        notebook.set_margin_bottom(8)
        notebook.set_margin_start(8)
        notebook.set_margin_end(8)
        overlay.set_child(notebook)

        notebook.append_page(self._build_status_page(), Gtk.Label(label="Status"))
        notebook.append_page(self._build_keys_page(), Gtk.Label(label="Keys"))
        notebook.append_page(self._build_actions_page(), Gtk.Label(label="Actions"))

        self.toast_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            valign=Gtk.Align.END,
            halign=Gtk.Align.CENTER,
        )
        self.toast_box.set_margin_bottom(24)
        overlay.add_overlay(self.toast_box)

        self._refresh_status()
        GLib.timeout_add_seconds(3, self._refresh_status_tick)

    # ----- pages --------------------------------------------------------

    def _build_status_page(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        scroll.set_child(outer)

        outer.append(section_label("Device"))

        device_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dev_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.device_dot = Gtk.Label(label="●")
        self.device_dot.add_css_class("status-dot")
        self.device_status = Gtk.Label(label="Checking…", xalign=0)
        self.device_status.set_hexpand(True)
        dev_row.append(self.device_dot)
        dev_row.append(self.device_status)
        device_box.append(dev_row)
        device_box.append(dim_label("USB 6603:1003 / HOTSPOTEKUSB HID DEMO"))
        outer.append(card(device_box))

        outer.append(section_label("Service"))
        svc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        svc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.svc_dot = Gtk.Label(label="●")
        self.svc_dot.add_css_class("status-dot")
        self.svc_status = Gtk.Label(label="Checking…", xalign=0)
        self.svc_status.set_hexpand(True)
        svc_row.append(self.svc_dot)
        svc_row.append(self.svc_status)
        svc_box.append(svc_row)

        self.svc_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.svc_buttons: dict[str, Gtk.Button] = {}
        for label, action in [("Start", "start"), ("Restart", "restart"), ("Stop", "stop")]:
            b = Gtk.Button(label=label)
            b.connect("clicked", self.on_service_action, action)
            self.svc_btn_box.append(b)
            self.svc_buttons[action] = b

        self.install_btn = Gtk.Button(label="Install service")
        self.install_btn.add_css_class("accent")
        self.install_btn.connect("clicked", self.on_install_service)
        self.svc_btn_box.append(self.install_btn)

        svc_box.append(self.svc_btn_box)
        svc_box.append(dim_label(SERVICE))
        outer.append(card(svc_box))

        outer.append(section_label("Brightness"))
        bright_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.brightness_adj = Gtk.Adjustment(
            lower=0, upper=100, step_increment=5, page_increment=10
        )
        self.brightness_adj.set_value(int(self.config.get("brightness", 80)))
        self.brightness_adj.connect("value-changed", self.on_brightness_changed)
        scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.brightness_adj
        )
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_digits(0)
        scale.set_hexpand(True)
        bright_box.append(scale)
        bright_box.append(dim_label("LCD backlight, 0–100. Applied on next service start."))
        outer.append(card(bright_box))

        return scroll

    def _build_keys_page(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        scroll.set_child(outer)

        outer.append(section_label("LCD Keys"))
        outer.append(dim_label(
            "Each key uses either a generated label+color icon or a custom image."
        ))

        self.key_widgets: dict[int, dict[str, Any]] = {}
        for k in LCD_KEYS:
            key_cfg = self.config.setdefault("keys", {}).setdefault(str(k), {})
            outer.append(card(self._build_key_card(k, key_cfg)))

        return scroll

    def _build_key_card(self, k: int, key_cfg: dict[str, Any]) -> Gtk.Widget:
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        pill = Gtk.Label(label=f"Key {k}")
        pill.add_css_class("key-pill")
        pill.set_valign(Gtk.Align.CENTER)
        header.append(pill)
        header.append(Gtk.Label(hexpand=True))

        # Segmented mode toggle
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        mode_box.add_css_class("linked")
        label_toggle = Gtk.ToggleButton(label="Label")
        image_toggle = Gtk.ToggleButton(label="Image")
        image_toggle.set_group(label_toggle)
        mode_box.append(label_toggle)
        mode_box.append(image_toggle)
        header.append(mode_box)

        pick_app_btn = Gtk.Button(label="Pick app…")
        pick_app_btn.set_tooltip_text("Use an installed application's icon and launch command")
        pick_app_btn.connect("clicked", self._on_pick_app, k)
        header.append(pick_app_btn)
        inner.append(header)

        # Body: preview on left, fields on right
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        preview_frame = Gtk.AspectFrame(ratio=1.0, obey_child=False)
        preview_frame.set_size_request(72, 72)
        preview = Gtk.DrawingArea()
        preview.set_content_width(72)
        preview.set_content_height(72)
        preview_frame.set_child(preview)
        body.append(preview_frame)

        fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        fields.set_hexpand(True)

        label_stack = Gtk.Stack()
        label_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        label_stack.set_transition_duration(120)

        # --- label/color mode ---
        label_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label_entry = Gtk.Entry()
        label_entry.set_text(str(key_cfg.get("label", "")))
        label_page.append(field_row("Label", label_entry))

        color_btn = Gtk.ColorButton()
        color_btn.set_rgba(parse_hex(key_cfg.get("color", "#1c63b8")))
        color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        color_box.append(color_btn)
        label_page.append(field_row("Color", color_box))
        label_stack.add_named(label_page, "label")

        # --- image mode ---
        image_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        path_entry = Gtk.Entry()
        path_entry.set_text(str(key_cfg.get("icon", "")))
        path_entry.set_placeholder_text("No image selected")
        path_entry.set_editable(False)
        path_entry.set_can_focus(False)

        choose_btn = Gtk.Button(label="Choose…")
        clear_btn = Gtk.Button(label="Clear")
        path_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        path_entry.set_hexpand(True)
        path_row.append(path_entry)
        path_row.append(choose_btn)
        path_row.append(clear_btn)
        image_page.append(field_row("Image", path_row))
        image_page.append(dim_label("Square images render best. Non-square will be center-cropped on the LCD."))
        label_stack.add_named(image_page, "image")

        fields.append(label_stack)

        # action stays in both modes
        action_entry = Gtk.Entry()
        action_entry.set_text(self._action_str(f"button.{k}.press"))
        action_entry.connect("changed", self.on_action_changed, f"button.{k}.press")
        fields.append(field_row("Press", action_entry))

        body.append(fields)
        inner.append(body)

        widgets: dict[str, Any] = {
            "label": label_entry,
            "color": color_btn,
            "action": action_entry,
            "path": path_entry,
            "preview": preview,
            "stack": label_stack,
            "label_toggle": label_toggle,
            "image_toggle": image_toggle,
        }
        self.key_widgets[k] = widgets

        # wire up
        label_entry.connect("changed", self._on_key_label_changed, k)
        color_btn.connect("color-set", self._on_key_color_set, k)
        choose_btn.connect("clicked", self._on_pick_image, k)
        clear_btn.connect("clicked", self._on_clear_image, k)
        label_toggle.connect("toggled", self._on_mode_toggle, k, "label")
        image_toggle.connect("toggled", self._on_mode_toggle, k, "image")
        preview.set_draw_func(self._draw_preview, k)

        self._sync_key_mode(k, initial=True)
        return inner

    # ---- per-key helpers -------------------------------------------------

    def _current_mode(self, k: int) -> str:
        cfg = self.config["keys"].get(str(k), {})
        return "image" if cfg.get("icon") else "label"

    def _sync_key_mode(self, k: int, initial: bool = False) -> None:
        mode = self._current_mode(k)
        w = self.key_widgets[k]
        if mode == "image":
            w["image_toggle"].set_active(True)
        else:
            w["label_toggle"].set_active(True)
        w["stack"].set_visible_child_name(mode)
        w["preview"].queue_draw()

    def _draw_preview(self, area: Gtk.DrawingArea, cr, width: int, height: int, k: int) -> None:
        cfg = self.config["keys"].get(str(k), {})
        icon_path = cfg.get("icon")
        size = min(width, height)
        ox = (width - size) / 2
        oy = (height - size) / 2

        if icon_path and Path(icon_path).is_file():
            try:
                from gi.repository import GdkPixbuf
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    icon_path, size, size, False  # crop (not preserve) for square
                )
                Gdk.cairo_set_source_pixbuf(cr, pb, ox, oy)
                cr.rectangle(ox, oy, size, size)
                cr.fill()
                return
            except Exception:  # noqa: BLE001
                log.exception("preview load failed for %s", icon_path)

        # label+color fallback
        rgba = parse_hex(cfg.get("color", "#1c63b8"))
        cr.set_source_rgb(rgba.red, rgba.green, rgba.blue)
        cr.rectangle(ox, oy, size, size)
        cr.fill()

        text = str(cfg.get("label", ""))[:6]
        if text:
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("Sans")
            cr.set_font_size(size * 0.32)
            ext = cr.text_extents(text)
            tx = ox + (size - ext.width) / 2 - ext.x_bearing
            ty = oy + (size + ext.height) / 2 - ext.y_bearing - ext.height / 2
            cr.move_to(tx, ty)
            cr.show_text(text)

    def _on_key_label_changed(self, entry: Gtk.Entry, k: int) -> None:
        self.config["keys"].setdefault(str(k), {})["label"] = entry.get_text()
        self.key_widgets[k]["preview"].queue_draw()
        self._mark_dirty()

    def _on_key_color_set(self, btn: Gtk.ColorButton, k: int) -> None:
        self.config["keys"].setdefault(str(k), {})["color"] = rgba_to_hex(btn.get_rgba())
        self.key_widgets[k]["preview"].queue_draw()
        self._mark_dirty()

    def _on_mode_toggle(self, btn: Gtk.ToggleButton, k: int, mode: str) -> None:
        if not btn.get_active():
            return
        w = self.key_widgets[k]
        cfg = self.config["keys"].setdefault(str(k), {})
        if mode == "label":
            cfg.pop("icon", None)
            w["path"].set_text("")
        else:
            # image mode requires an icon; if none chosen yet, just switch view
            pass
        w["stack"].set_visible_child_name(mode)
        w["preview"].queue_draw()
        self._mark_dirty()

    def _on_pick_image(self, _btn: Gtk.Button, k: int) -> None:
        dlg = Gtk.FileDialog()
        dlg.set_title(f"Choose image for key {k}")
        img_filter = Gtk.FileFilter()
        img_filter.set_name("Images")
        for pat in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.gif"):
            img_filter.add_pattern(pat)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(img_filter)
        dlg.set_filters(filters)
        dlg.set_default_filter(img_filter)

        def cb(dialog: Gtk.FileDialog, result) -> None:
            try:
                f = dialog.open_finish(result)
            except GLib.Error as exc:
                log.info("file dialog cancelled: %s", exc.message)
                return
            if f is None:
                return
            path = f.get_path()
            cfg = self.config["keys"].setdefault(str(k), {})
            cfg["icon"] = path
            w = self.key_widgets[k]
            w["path"].set_text(path)
            w["image_toggle"].set_active(True)
            w["stack"].set_visible_child_name("image")
            w["preview"].queue_draw()
            self._mark_dirty()

        dlg.open(self, None, cb)

    def _on_pick_app(self, _btn: Gtk.Button, k: int) -> None:
        def chosen(app: Gio.AppInfo) -> None:
            cmd_raw = app.get_commandline() or app.get_executable() or ""
            cmd = strip_exec_codes(cmd_raw)
            icon_path = icon_path_for_app(app)
            cfg = self.config["keys"].setdefault(str(k), {})
            if icon_path:
                cfg["icon"] = icon_path
            else:
                cfg.pop("icon", None)
            actions = self.config.setdefault("actions", {})
            event = f"button.{k}.press"
            if cmd:
                actions[event] = cmd
            w = self.key_widgets[k]
            w["path"].set_text(icon_path or "")
            w["action"].set_text(cmd)
            if icon_path:
                w["image_toggle"].set_active(True)
                w["stack"].set_visible_child_name("image")
            else:
                w["label_toggle"].set_active(True)
                w["stack"].set_visible_child_name("label")
            w["preview"].queue_draw()
            self._mark_dirty()
            self.toast(f"Key {k}: {app.get_display_name()}")

        dlg = AppPickerDialog(self, chosen)
        dlg.present()

    def _on_clear_image(self, _btn: Gtk.Button, k: int) -> None:
        cfg = self.config["keys"].setdefault(str(k), {})
        cfg.pop("icon", None)
        w = self.key_widgets[k]
        w["path"].set_text("")
        w["label_toggle"].set_active(True)
        w["stack"].set_visible_child_name("label")
        w["preview"].queue_draw()
        self._mark_dirty()

    def _build_actions_page(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        scroll.set_child(outer)

        self.action_entries: dict[str, Gtk.Entry] = {}

        outer.append(section_label("Round Buttons"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for k in ROUND_BUTTONS:
            event = f"button.{k}.press"
            entry = Gtk.Entry()
            entry.set_text(self._action_str(event))
            entry.connect("changed", self.on_action_changed, event)
            self.action_entries[event] = entry
            box.append(field_row(ROUND_LABELS[k], entry))
        outer.append(card(box))

        for k in KNOBS:
            outer.append(section_label(KNOB_LABELS[k]))
            kbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            for direction in ("left", "right", "press"):
                event = f"knob.{k}.{direction}"
                entry = Gtk.Entry()
                entry.set_text(self._action_str(event))
                entry.connect("changed", self.on_action_changed, event)
                self.action_entries[event] = entry
                kbox.append(field_row(direction.capitalize(), entry))
            outer.append(card(kbox))

        return scroll

    # ----- helpers ------------------------------------------------------

    def _action_str(self, event: str) -> str:
        val = self.config.get("actions", {}).get(event, "")
        if isinstance(val, list):
            return " && ".join(val)
        return str(val)

    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self.save_btn.set_sensitive(True)

    def _refresh_status_tick(self) -> bool:
        self._refresh_status()
        return True

    def _refresh_status(self) -> None:
        present = device_present()
        self.device_status.set_text("Connected" if present else "Not detected")
        self.device_dot.remove_css_class("status-ok")
        self.device_dot.remove_css_class("status-bad")
        self.device_dot.add_css_class("status-ok" if present else "status-bad")

        installed = service_installed()
        active = service_active() if installed else False
        if not installed:
            self.svc_status.set_text("Not installed")
        else:
            self.svc_status.set_text("Active" if active else "Inactive")
        self.svc_dot.remove_css_class("status-ok")
        self.svc_dot.remove_css_class("status-bad")
        self.svc_dot.add_css_class("status-ok" if active else "status-bad")
        for btn in self.svc_buttons.values():
            btn.set_sensitive(installed)
        self.install_btn.set_visible(not installed)

    def toast(self, text: str) -> None:
        rev = Gtk.Revealer()
        rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        rev.set_transition_duration(180)
        lbl = Gtk.Label(label=text)
        lbl.add_css_class("toast")
        rev.set_child(lbl)
        self.toast_box.append(rev)
        rev.set_reveal_child(True)

        def dismiss() -> bool:
            rev.set_reveal_child(False)
            GLib.timeout_add(220, lambda: (self.toast_box.remove(rev), False)[1])
            return False

        GLib.timeout_add_seconds(3, dismiss)

    # ----- callbacks ----------------------------------------------------

    def on_brightness_changed(self, adj: Gtk.Adjustment) -> None:
        self.config["brightness"] = int(adj.get_value())
        self._mark_dirty()

    def on_action_changed(self, entry: Gtk.Entry, event: str) -> None:
        actions = self.config.setdefault("actions", {})
        text = entry.get_text().strip()
        if text:
            actions[event] = text
        else:
            actions.pop(event, None)
        self._mark_dirty()

    def on_save(self, _btn: Gtk.Button) -> None:
        log.info("save clicked")
        try:
            save_config(self.config)
        except Exception as exc:  # noqa: BLE001
            log.exception("save_config failed")
            self.toast(f"Save failed: {exc}")
            return
        self._dirty = False
        self.save_btn.set_sensitive(False)
        if service_active():
            ok, _ = systemctl("restart")
            self.toast("Saved · service restarted" if ok else "Saved · restart failed")
        else:
            self.toast("Saved to disk")

    def on_reload(self, _btn: Gtk.Button) -> None:
        try:
            self.config = load_config()
        except Exception as exc:  # noqa: BLE001
            self.toast(f"Reload failed: {exc}")
            return
        self.brightness_adj.set_value(int(self.config.get("brightness", 80)))
        for k, w in self.key_widgets.items():
            cfg = self.config.get("keys", {}).get(str(k), {})
            w["label"].set_text(str(cfg.get("label", "")))
            w["color"].set_rgba(parse_hex(cfg.get("color", "#1c63b8")))
            w["action"].set_text(self._action_str(f"button.{k}.press"))
            w["path"].set_text(str(cfg.get("icon", "")))
            self._sync_key_mode(k)
            w["preview"].queue_draw()
        for event, entry in self.action_entries.items():
            entry.set_text(self._action_str(event))
        self._dirty = False
        self.save_btn.set_sensitive(False)
        self.toast("Reloaded from disk")

    def on_install_service(self, _btn: Gtk.Button) -> None:
        log.info("install service clicked")
        if not SERVICE_SRC.exists():
            self.toast(f"Service template missing: {SERVICE_SRC}")
            return
        ok, msg = install_service()
        self.toast("Service installed" if ok else f"Install failed: {msg}")
        self._refresh_status()

    def on_service_action(self, _btn: Gtk.Button, action: str) -> None:
        log.info("service action: %s", action)
        if not shutil.which("systemctl"):
            self.toast("systemctl not found")
            return
        ok, msg = systemctl(action)
        self.toast(f"{action}: {'ok' if ok else 'failed — see /tmp/streamdock-n3-gui.log'}")
        if not ok:
            log.warning("service %s failed: %s", action, msg)
        self._refresh_status()


# ----- theme loader -------------------------------------------------------


class ThemeLoader:
    def __init__(self) -> None:
        self.provider = Gtk.CssProvider()
        self.apply()
        self._monitor: Gio.FileMonitor | None = None
        if OMARCHY_THEME.exists():
            gfile = Gio.File.new_for_path(str(OMARCHY_THEME))
            try:
                self._monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
                self._monitor.connect("changed", self._on_changed)
            except Exception:  # noqa: BLE001
                self._monitor = None

    def apply(self) -> None:
        palette = parse_palette(OMARCHY_THEME)
        css = build_css(palette)
        self.provider.load_from_string(css)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _on_changed(self, *_args: Any) -> None:
        GLib.timeout_add(150, lambda: (self.apply(), False)[1])


# ----- application --------------------------------------------------------


class StreamDockApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.theme: ThemeLoader | None = None

    def do_startup(self) -> None:  # type: ignore[override]
        Gtk.Application.do_startup(self)
        self.theme = ThemeLoader()

    def do_activate(self) -> None:  # type: ignore[override]
        win = self.props.active_window or StreamDockWindow(self)
        win.present()


def main() -> int:
    log.info("=== startup ===")
    log.info("argv=%s", sys.argv)
    log.info("python=%s", sys.executable)
    log.info("cwd=%s", os.getcwd())
    log.info("CONFIG_PATH=%s exists=%s", CONFIG_PATH, CONFIG_PATH.exists())
    log.info("DISPLAY=%s WAYLAND_DISPLAY=%s", os.environ.get("DISPLAY"), os.environ.get("WAYLAND_DISPLAY"))
    log.info("PATH=%s", os.environ.get("PATH"))
    if not CONFIG_PATH.exists():
        log.error("config not found: %s", CONFIG_PATH)
        print(f"config not found: {CONFIG_PATH}", file=sys.stderr)
        return 1
    try:
        return StreamDockApp().run(sys.argv)
    except Exception:
        log.exception("app run failed")
        raise


if __name__ == "__main__":
    raise SystemExit(main())

"""Icon generation and color parsing for LCD keys."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

FALLBACK_COLORS: list[tuple[int, int, int]] = [
    (28, 99, 184),
    (24, 132, 82),
    (181, 83, 36),
    (132, 68, 168),
    (50, 122, 138),
    (174, 54, 92),
]


def parse_color(value: Any, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not isinstance(value, str):
        return fallback
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def make_icon(
    label: str,
    color: tuple[int, int, int],
    path: Path,
    text_color: tuple[int, int, int] = (255, 255, 255),
) -> None:
    image = Image.new("RGB", (64, 64), color)
    draw = ImageDraw.Draw(image)
    size = 26 if len(label) <= 3 else 18 if len(label) <= 5 else 14
    font = ImageFont.load_default(size=size)
    lines = label.split("\\n")
    line_boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_height = max(box[3] - box[1] for box in line_boxes)
    total_height = line_height * len(lines) + 2 * (len(lines) - 1)
    y = (image.height - total_height) // 2
    for line, box in zip(lines, line_boxes, strict=True):
        width = box[2] - box[0]
        x = (image.width - width) // 2
        draw.text((x, y), line, fill=text_color, font=font)
        y += line_height + 2
    image.save(path, "JPEG", quality=95)

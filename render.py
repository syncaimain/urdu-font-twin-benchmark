"""Deterministic single-font Urdu shaping and rasterization."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

RENDER_DEPS = Path(__file__).resolve().parent / ".render-deps"
if RENDER_DEPS.exists():
    sys.path.insert(0, str(RENDER_DEPS))

import freetype  # type: ignore
import uharfbuzz as hb  # type: ignore
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont


CALIBRATION_TEXT = "پاکستان میں اردو کی خوبصورت تحریر پڑھی جاتی ہے۔"
DEFAULT_CANVAS = (1600, 720)


@dataclass(frozen=True)
class FontSpec:
    key: str
    label: str
    path: Path


FONT_SPECS = {
    "nastaliq": FontSpec(
        "nastaliq", "Noto Nastaliq Urdu", Path("assets/fonts/NotoNastaliqUrdu-VF.ttf")
    ),
    "naskh": FontSpec("naskh", "Noto Naskh Arabic", Path("assets/fonts/NotoNaskhArabic-VF.ttf")),
}


@dataclass
class ShapedGlyph:
    glyph_id: int
    cluster: int
    x: float
    y_offset: float


@dataclass
class ShapedLine:
    glyphs: list[ShapedGlyph]
    advance: float


class UrduRenderer:
    """Shapes with HarfBuzz and draws only glyphs from the requested font."""

    def __init__(self, font_path: Path, pixel_size: int):
        self.font_path = Path(font_path)
        self.pixel_size = int(pixel_size)
        self.font_bytes = self.font_path.read_bytes()
        self.ft_face = freetype.Face(str(self.font_path))
        self.ft_face.set_pixel_sizes(0, self.pixel_size)
        self.hb_face = hb.Face(self.font_bytes)
        self.hb_font = hb.Font(self.hb_face)
        self.hb_font.scale = (self.hb_face.upem, self.hb_face.upem)
        hb.ot_font_set_funcs(self.hb_font)
        self.scale = self.pixel_size / self.hb_face.upem

    def shape(
        self,
        text: str,
        direction: str = "rtl",
        script: str = "Arab",
        language: str = "ur",
    ) -> ShapedLine:
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.direction = direction
        buffer.script = script
        buffer.language = language
        hb.shape(self.hb_font, buffer, {"kern": True, "liga": True, "rlig": True})
        glyphs: list[ShapedGlyph] = []
        pen_x = 0.0
        for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions):
            glyphs.append(
                ShapedGlyph(
                    glyph_id=info.codepoint,
                    cluster=info.cluster,
                    x=pen_x + pos.x_offset * self.scale,
                    y_offset=pos.y_offset * self.scale,
                )
            )
            pen_x += pos.x_advance * self.scale
        return ShapedLine(glyphs=glyphs, advance=pen_x)

    def _glyph_bitmaps(self, line: ShapedLine) -> tuple[list[tuple], tuple[int, int, int, int]]:
        rendered: list[tuple] = []
        left = top = math.inf
        right = bottom = -math.inf
        for item in line.glyphs:
            self.ft_face.load_glyph(item.glyph_id, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
            slot = self.ft_face.glyph
            bitmap = slot.bitmap
            width, rows = int(bitmap.width), int(bitmap.rows)
            x = item.x + slot.bitmap_left
            y = -(slot.bitmap_top + item.y_offset)
            if width and rows:
                pixels = bytes(bitmap.buffer)
                mask = Image.frombytes("L", (width, rows), pixels)
                rendered.append((mask, x, y, item.glyph_id, item.cluster))
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x + width), max(bottom, y + rows)
        if not rendered:
            return rendered, (0, 0, 0, 0)
        return rendered, (math.floor(left), math.floor(top), math.ceil(right), math.ceil(bottom))

    def measure(
        self,
        text: str,
        direction: str = "rtl",
        script: str = "Arab",
        language: str = "ur",
    ) -> tuple[int, int]:
        _, bounds = self._glyph_bitmaps(self.shape(text, direction, script, language))
        return bounds[2] - bounds[0], bounds[3] - bounds[1]

    def render_line(
        self,
        text: str,
        direction: str = "rtl",
        script: str = "Arab",
        language: str = "ur",
    ) -> Image.Image:
        glyphs, bounds = self._glyph_bitmaps(self.shape(text, direction, script, language))
        width = max(1, bounds[2] - bounds[0])
        height = max(1, bounds[3] - bounds[1])
        image = Image.new("L", (width, height), 255)
        for mask, x, y, _, _ in glyphs:
            image.paste(0, (round(x - bounds[0]), round(y - bounds[1])), mask)
        return image

    def wrap(
        self,
        text: str,
        max_width: int,
        direction: str = "rtl",
        script: str = "Arab",
        language: str = "ur",
    ) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join(current + [word])
            if current and self.measure(candidate, direction, script, language)[0] > max_width:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        lines.append(" ".join(current))
        return lines

    def render(
        self,
        text: str,
        canvas: tuple[int, int] = DEFAULT_CANVAS,
        margin: int = 48,
        direction: str = "rtl",
        script: str = "Arab",
        language: str = "ur",
    ) -> Image.Image:
        lines = self.wrap(text, canvas[0] - 2 * margin, direction, script, language)
        line_images = [self.render_line(line, direction, script, language) for line in lines]
        line_gap = max(12, round(self.pixel_size * 0.28))
        total_height = sum(image.height for image in line_images) + line_gap * (len(lines) - 1)
        if total_height > canvas[1] - 2 * margin:
            raise ValueError(f"Text needs {total_height}px vertically but canvas permits {canvas[1] - 2 * margin}px")
        output = Image.new("L", canvas, 255)
        y = (canvas[1] - total_height) // 2
        for line_image in line_images:
            x = canvas[0] - margin - line_image.width
            output.paste(line_image, (x, y))
            y += line_image.height + line_gap
        return output


def visible_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    return Image.eval(image, lambda px: 255 - px).getbbox()


def _median_word_height(renderer: UrduRenderer, text: str) -> int:
    return round(statistics.median(renderer.measure(word)[1] for word in text.split()))


def calibrate_pixel_size(font_path: Path, target_visible_height: int = 78) -> tuple[int, int]:
    best = (16, 0)
    for size in range(16, 201):
        renderer = UrduRenderer(font_path, size)
        height = _median_word_height(renderer, CALIBRATION_TEXT)
        if abs(height - target_visible_height) < abs(best[1] - target_visible_height):
            best = (size, height)
        if height >= target_visible_height:
            break
    return best


def font_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font_codepoints(path: Path) -> set[int]:
    font = TTFont(path, lazy=True)
    return {cp for table in font["cmap"].tables for cp in table.cmap}


def create_contact_sheet(records: Iterable[dict], output: Path) -> None:
    rows = list(records)
    grouped: dict[str, dict[str, dict]] = {}
    for record in rows:
        if record.get("resolution") != "canonical":
            continue
        grouped.setdefault(record["pair_id"], {})[record["font_key"]] = record
    pairs = [item for item in grouped.values() if set(item) == {"nastaliq", "naskh"}]
    thumb_size = (600, 270)
    label_width, header_height, gap = 150, 46, 10
    sheet = Image.new("RGB", (label_width + 2 * thumb_size[0] + gap, header_height + len(pairs) * thumb_size[1]), "white")
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.load_default(size=16)
    draw.text((label_width + 10, 12), "Noto Nastaliq Urdu", fill="black", font=label_font)
    draw.text((label_width + thumb_size[0] + gap + 10, 12), "Noto Naskh Arabic", fill="black", font=label_font)
    for row_index, pair in enumerate(pairs):
        y = header_height + row_index * thumb_size[1]
        left_record = pair["nastaliq"]
        draw.text((8, y + 8), f"{left_record['source_id']}\n{left_record['condition']}", fill="black", font=label_font)
        for col, key in enumerate(("nastaliq", "naskh")):
            image = Image.open(pair[key]["image_path"]).convert("RGB")
            image.thumbnail(thumb_size, Image.Resampling.LANCZOS)
            x = label_width + col * (thumb_size[0] + gap)
            sheet.paste(image, (x, y))
        draw.line((0, y + thumb_size[1] - 1, sheet.width, y + thumb_size[1] - 1), fill="#dddddd")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def calibration_report(output: Path = Path("assets/font_calibration.json")) -> dict:
    report = {
        "target_median_word_visible_height_px": 78,
        "calibration_metric": "median per-word ink bounding-box height",
        "calibration_text": CALIBRATION_TEXT,
        "fonts": {},
    }
    for key, spec in FONT_SPECS.items():
        size, height = calibrate_pixel_size(spec.path)
        report["fonts"][key] = {
            "label": spec.label,
            "path": str(spec.path).replace("\\", "/"),
            "sha256": font_sha256(spec.path),
            "pixel_size": size,
            "measured_median_word_visible_height_px": height,
        }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(calibration_report(), ensure_ascii=False, indent=2))

import io
import os

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from . import config

# Base-14 PDF fonts exposed to the admin (short name -> pretty label).
FONTS = {
    "helv": "Helvetica",
    "hebo": "Helvetica Bold",
    "tiro": "Times Roman",
    "tibo": "Times Bold",
    "cour": "Courier",
}

# Candidate TTF font files used for image templates, checked in order across
# macOS, Linux and Windows. Falls back to Pillow's default if none are found.
FONT_CANDIDATES = {
    "helv": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "hebo": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
    "tiro": [
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "C:/Windows/Fonts/times.ttf",
    ],
    "tibo": [
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "C:/Windows/Fonts/timesbd.ttf",
    ],
    "cour": [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "C:/Windows/Fonts/cour.ttf",
    ],
}


def detect_template(data: bytes):
    """Return (template_type, extension) for uploaded template bytes."""
    if data[:4] == b"%PDF":
        return "pdf", "pdf"
    try:
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").lower()
        if fmt == "png":
            return "image", "png"
        if fmt in ("jpeg", "jpg"):
            return "image", "jpg"
    except Exception:
        pass
    return None, None


def _load_font(font: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES.get(font, []):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _zoom_for(page_width: float) -> float:
    target = config.RENDER_TARGET_WIDTH
    zoom = target / page_width if page_width else 3.0
    return max(2.0, min(zoom, 6.0))


def render_pdf_preview(pdf_path: str):
    """Render the first page of a PDF template to a pixmap (for admin preview)."""
    doc = pymupdf.open(pdf_path)
    try:
        page = doc[0]
        zoom = _zoom_for(page.rect.width)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pix
    finally:
        doc.close()


def render_image_preview(img_path: str) -> bytes:
    """Resize an image template for admin preview, returning PNG bytes."""
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    target = config.RENDER_TARGET_WIDTH
    if w > target:
        img = img.resize((target, round(h * target / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _hex_to_rgb01(hex_color: str):
    """Convert '#RRGGBB' to a (r, g, b) tuple of floats in [0, 1]."""
    return tuple(v / 255.0 for v in _hex_to_rgb(hex_color))


def _hex_to_rgb(hex_color: str):
    """Convert '#RRGGBB' (or bare RRGGBB) to an (r, g, b) tuple of ints 0-255."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return (0, 0, 0)
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def render_pdf_certificate(pdf_path: str, name: str, position: dict, font_size: float, font: str, color: str = "#000000"):
    """Insert the name into a PDF template and render it to a pixmap."""
    font = font if font in FONTS else "helv"
    font_size = float(font_size) if font_size else 24.0

    doc = pymupdf.open(pdf_path)
    try:
        page = doc[0]
        pw, ph = page.rect.width, page.rect.height

        cx = position.get("x", 0.5) * pw
        cy = position.get("y", 0.5) * ph

        text_w = pymupdf.get_text_length(name, fontname=font, fontsize=font_size)
        x = cx - text_w / 2.0
        baseline_y = cy + font_size * 0.35

        page.insert_text(
            (x, baseline_y),
            name,
            fontname=font,
            fontsize=font_size,
            color=_hex_to_rgb01(color),
        )

        zoom = _zoom_for(pw)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pix
    finally:
        doc.close()


def render_image_certificate(img_path: str, name: str, position: dict, font_size: float, font: str, color: str = "#000000"):
    """Overlay the name onto an image template and return PNG bytes."""
    font = font if font in FONTS else "helv"
    font_size = float(font_size) if font_size else 24.0

    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    target = config.RENDER_TARGET_WIDTH
    if w < target:
        img = img.resize((target, round(h * target / w)), Image.LANCZOS)
        w, h = img.size

    font_px = max(1, round(font_size / config.REF_PAGE_WIDTH * w))
    font_obj = _load_font(font, font_px)

    cx = position.get("x", 0.5) * w
    cy = position.get("y", 0.5) * h

    draw = ImageDraw.Draw(img)
    draw.text((cx, cy), name, font=font_obj, fill=_hex_to_rgb(color), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

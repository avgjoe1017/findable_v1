"""OpenGraph image generator for shareable Findable Score results.

Generates a 1200x630px PNG with a score ring, domain name, level label,
and branding -- suitable for social sharing previews (og:image).
"""

from __future__ import annotations

import io
import math
from pathlib import Path

import structlog
from PIL import Image, ImageDraw, ImageFont

logger = structlog.get_logger(__name__)

# Canvas (OpenGraph standard)
WIDTH, HEIGHT = 1200, 630

# Dark theme palette
BG_COLOR = "#0a0f1a"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#94a3b8"
RING_BG = "#1e293b"
COLOR_TEAL = "#14b8a6"
COLOR_YELLOW = "#eab308"
COLOR_ORANGE = "#f97316"
COLOR_RED = "#ef4444"

# Layout
RING_CENTER_X, RING_CENTER_Y = WIDTH // 2, 280
RING_RADIUS, RING_WIDTH = 120, 14
MAX_DOMAIN_LEN = 40


def _score_color(score: int) -> str:
    """Return the ring color based on score thresholds."""
    if score >= 70:
        return COLOR_TEAL
    if score >= 55:
        return COLOR_YELLOW
    if score >= 40:
        return COLOR_ORANGE
    return COLOR_RED


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font, falling back to PIL default."""
    for name in [
        "arial.ttf",
        "Arial.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    logger.warning("no_truetype_font_found", fallback="default")
    return ImageFont.load_default()


def _truncate_domain(domain: str, max_len: int = MAX_DOMAIN_LEN) -> str:
    """Truncate long domain names with an ellipsis."""
    if len(domain) <= max_len:
        return domain
    return domain[: max_len - 1] + "\u2026"


def _draw_ring(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int,
    width: int,
    score: int,
    color: str,
) -> None:
    """Draw a circular progress ring for the score."""
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    draw.arc(bbox, start=0, end=360, fill=RING_BG, width=width)

    sweep = (score / 100) * 360
    if sweep > 0:
        draw.arc(bbox, start=-90, end=-90 + sweep, fill=color, width=width)

    # Rounded end-caps
    cap_r = width // 2
    sx = cx + radius * math.cos(math.radians(-90))
    sy = cy + radius * math.sin(math.radians(-90))
    draw.ellipse(
        [sx - cap_r, sy - cap_r, sx + cap_r, sy + cap_r],
        fill=color if score > 0 else RING_BG,
    )
    if score > 0:
        end_deg = -90 + sweep
        ex = cx + radius * math.cos(math.radians(end_deg))
        ey = cy + radius * math.sin(math.radians(end_deg))
        draw.ellipse([ex - cap_r, ey - cap_r, ex + cap_r, ey + cap_r], fill=color)


def _centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
) -> None:
    """Draw horizontally centered text at the given y coordinate."""
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text(((WIDTH - (bb[2] - bb[0])) // 2, y), text, font=font, fill=fill)


def generate_og_image(
    score: int,
    domain: str,
    level_label: str,
    output_path: Path | str | None = None,
) -> bytes:
    """Generate an OpenGraph image for a Findable Score result.

    Args:
        score: Findable Score (0-100)
        domain: Website domain (e.g., "example.com")
        level_label: Findability level (e.g., "Highly Findable")
        output_path: Optional path to save the PNG file

    Returns:
        PNG image bytes
    """
    score = max(0, min(100, score))
    domain = _truncate_domain(domain.strip())
    color = _score_color(score)
    logger.info("generating_og_image", score=score, domain=domain, level=level_label)

    # Fonts
    f_title = _load_font(28)
    f_score = _load_font(72)
    f_denom = _load_font(24)
    f_domain = _load_font(30)
    f_level = _load_font(22)
    f_brand = _load_font(18)

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Title
    _centered(draw, 50, "Findable Score", f_title, TEXT_SECONDARY)

    # Score ring
    _draw_ring(draw, RING_CENTER_X, RING_CENTER_Y, RING_RADIUS, RING_WIDTH, score, color)

    # Score number inside ring
    s_text = str(score)
    s_bb = draw.textbbox((0, 0), s_text, font=f_score)
    s_w, s_h = s_bb[2] - s_bb[0], s_bb[3] - s_bb[1]
    draw.text(
        (RING_CENTER_X - s_w // 2, RING_CENTER_Y - s_h // 2 - 12),
        s_text,
        font=f_score,
        fill=color,
    )

    # "/100" denominator
    d_bb = draw.textbbox((0, 0), "/100", font=f_denom)
    draw.text(
        (RING_CENTER_X - (d_bb[2] - d_bb[0]) // 2, RING_CENTER_Y + s_h // 2 - 6),
        "/100",
        font=f_denom,
        fill=TEXT_SECONDARY,
    )

    # Domain and level
    _centered(draw, 440, domain, f_domain, TEXT_PRIMARY)
    _centered(draw, 482, level_label, f_level, color)

    # Branding footer
    _centered(draw, 580, "getfindable.online", f_brand, TEXT_SECONDARY)

    # Export
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(png_bytes)
        logger.info("og_image_saved", path=str(out), size_kb=len(png_bytes) // 1024)

    return png_bytes

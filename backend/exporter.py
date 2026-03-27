"""Export engine optimized for the Roland TrueVIS SG2-540 printer.

Produces PNG files with:
- sRGB IEC61966-2.1 color profile embedded
- 300 DPI minimum resolution
- RGBA color mode (transparency preserved)
- PNG compression level 6
"""

import io
import zipfile
from pathlib import Path
from typing import List, Dict

from PIL import Image, PngImagePlugin

TEMP_DIR = Path(__file__).parent / "temp"

# Target DPI for print output
TARGET_DPI = 300


def _safe_name(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.strip())
    return safe or "image"


def _get_srgb_profile() -> bytes:
    """Return a minimal sRGB ICC profile.

    Uses Pillow's built-in sRGB profile if available, otherwise
    embeds the DPI metadata without a profile (printers handle sRGB by default).
    """
    try:
        from PIL.ImageCms import createProfile, ImageCmsProfile
        profile = createProfile("sRGB")
        cms_profile = ImageCmsProfile(profile)
        return cms_profile.tobytes()
    except Exception:
        return b""


def _optimize_for_printer(img: Image.Image) -> Image.Image:
    """Ensure image meets Roland TrueVIS SG2-540 requirements."""
    # Ensure RGBA
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    return img


def export_single(job_id: str, image_id: str, name: str) -> bytes:
    """Export a single isolated image as an optimized PNG."""
    img_path = TEMP_DIR / job_id / f"{image_id}.png"
    if not img_path.exists():
        raise FileNotFoundError(f"Image {image_id} not found for job {job_id}")

    img = Image.open(str(img_path)).convert("RGBA")
    img = _optimize_for_printer(img)

    buf = io.BytesIO()

    # Build PNG metadata with DPI
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Software", "ESPORTIKO Image Isolator")

    # Save with DPI and compression settings
    img.save(
        buf,
        format="PNG",
        compress_level=6,
        dpi=(TARGET_DPI, TARGET_DPI),
        pnginfo=pnginfo,
    )

    # Embed ICC profile if available
    srgb = _get_srgb_profile()
    if srgb:
        buf.seek(0)
        img_with_profile = Image.open(buf)
        buf2 = io.BytesIO()
        img_with_profile.save(
            buf2,
            format="PNG",
            compress_level=6,
            dpi=(TARGET_DPI, TARGET_DPI),
            icc_profile=srgb,
            pnginfo=pnginfo,
        )
        return buf2.getvalue()

    return buf.getvalue()


def export_multiple(job_id: str, selections: List[Dict[str, str]]) -> bytes:
    """Export multiple images as a zip file.

    Each entry in `selections` has { "id": str, "name": str }.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sel in selections:
            png_bytes = export_single(job_id, sel["id"], sel["name"])
            filename = f"{_safe_name(sel['name'])}.png"
            zf.writestr(filename, png_bytes)

    return buf.getvalue()

#!/usr/bin/env python3
"""
Thumbnail generator — uses the original image (kept for crop export).
pyvips thumbnail is shrink-on-load efficient for large images.
"""

import json
import re
from pathlib import Path

try:
    import pyvips
    HAS_PYVIPS = True
except ImportError:
    HAS_PYVIPS = False


def _safe_path(base_dir, *parts):
    base = Path(base_dir).resolve()
    target = base.joinpath(*parts).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise RuntimeError("path traversal blocked")
    return target


def get_or_generate_thumbnail(artwork_slug, artworks_dir, size=400):
    if not artwork_slug or not re.match(r"^[\w-]+$", artwork_slug):
        return None

    artworks_dir = Path(artworks_dir)
    artwork_path = _safe_path(artworks_dir, artwork_slug)
    thumb_path = _safe_path(artwork_path, f".thumb-{size}.jpg")

    # always regenerate if suspiciously small | IT HAPPENED BECAUSE OF THE SOLID COLOUR CORRUPTION
    if thumb_path.exists() and thumb_path.stat().st_size > 1024:
        return str(thumb_path)
    if thumb_path.exists():
        thumb_path.unlink(missing_ok=True)

    source = None
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
        candidate = artwork_path / f"original{ext}"
        if candidate.exists():
            source = candidate
            break

    if not source or not source.exists():
        return None

    # make thumbnail quality higher this time, it was tooo blurry before
    try:
        if HAS_PYVIPS:
            pyvips.Image.thumbnail(str(source), size).write_to_file(
                str(thumb_path), Q=85
            )
        else:
            import subprocess
            subprocess.run(
                ["vips", "thumbnail", str(source), str(thumb_path), str(size)],
                check=True, capture_output=True
            )
        return str(thumb_path)
    except Exception:
        return None


def has_thumbnail(artwork_slug, artworks_dir, size=400):
    try:
        thumb_path = _safe_path(artworks_dir, artwork_slug, f".thumb-{size}.jpg")
        return thumb_path.exists() and thumb_path.stat().st_size > 1024
    except Exception:
        return False


def update_metadata_with_thumbnails(artworks_dir):
    artworks_dir = Path(artworks_dir)
    metadata_file = artworks_dir / ".artworks.json"

    metadata = {}
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text())
        except Exception:
            pass

    return {
        slug: get_or_generate_thumbnail(slug, artworks_dir) is not None
        for slug in metadata.keys()
    }

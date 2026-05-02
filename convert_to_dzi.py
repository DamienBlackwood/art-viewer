#!/usr/bin/env python3
"""
Convert images to Deep Zoom Image (DZI) format for the gallery viewer.
Keeps the original image for high-res crop export.

Usage:
  python3 convert_to_dzi.py image.jpg
  python3 convert_to_dzi.py image.jpg --cleanup   # delete original after conversion
"""

import sys
import json
import re
import argparse
from pathlib import Path

try:
    import pyvips
    HAS_PYVIPS = True
except ImportError:
    HAS_PYVIPS = False
    import subprocess

from thumb_utils import get_or_generate_thumbnail


def _safe_slug(name):
    """Create a filesystem-safe slug from a name."""
    if not name:
        return "artwork"
    slug = re.sub(r"[^\w\s-]", "", name)
    slug = re.sub(r"[-\s]+", "-", slug)
    slug = slug.lower().strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:80] or "artwork"


def _safe_path(base_dir, *parts):
    """Join path parts and ensure the result stays inside base_dir."""
    base = Path(base_dir).resolve()
    target = base.joinpath(*parts).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise RuntimeError("path traversal blocked")
    return target


def show_progress(image, progress):
    bar_len = 40
    filled = int(bar_len * progress.percent / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    eta = f"{progress.eta:.0f}s" if progress.eta > 0 else "calculating"
    out = f"\r[{bar}] {progress.percent:3d}% | {progress.run:.1f}s | {eta} left"
    print(out[:80], end="", flush=True)


def process_image(src, artworks_dir, cleanup=False, original_name=None):
    """
    Convert an image file to DZI and return artwork metadata dict.
    Keeps the original image for crop export.
    `original_name` overrides the filename-derived name (useful for uploads).
    """
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"file not found: {src}")

    original_name = original_name or src.stem
    slug = _safe_slug(original_name)

    artworks_dir = Path(artworks_dir)
    artworks_dir.mkdir(exist_ok=True)

    # deduplicate slug
    dzi_dir = _safe_path(artworks_dir, slug)
    if dzi_dir.exists():
        counter = 1
        while True:
            new_slug = f"{slug}-{counter}"
            dzi_dir = _safe_path(artworks_dir, new_slug)
            if not dzi_dir.exists():
                slug = new_slug
                break
            counter += 1
            if counter > 999:
                raise RuntimeError("too many artworks with similar names")

    dzi_dir.mkdir(exist_ok=True)

    # keep original for crop export
    original_ext = src.suffix or ".jpg"
    original_dest = _safe_path(dzi_dir, f"original{original_ext}")
    original_dest.write_bytes(src.read_bytes())

    # also copy for processing if pyvips needs it in a specific place
    working_copy = _safe_path(dzi_dir, src.name)
    working_copy.write_bytes(src.read_bytes())

    try:
        if HAS_PYVIPS:
            _convert_with_pyvips(working_copy, dzi_dir, slug)
        else:
            print("\npyvips not found, falling back to vips CLI (no progress bar)...")
            _convert_with_cli(working_copy, dzi_dir, slug)

        get_or_generate_thumbnail(slug, artworks_dir)

        dzi_file = dzi_dir / f"{slug}.dzi"
        _save_metadata(slug, original_name, dzi_file, artworks_dir)

        return {
            "name": original_name,
            "slug": slug,
            "path": f"Artworks/{slug}/{slug}.dzi",
            "thumbnail": f"/api/thumb/{slug}",
            "original": f"Artworks/{slug}/original{original_ext}",
        }

    finally:
        working_copy.unlink(missing_ok=True)
        if cleanup:
            src.unlink(missing_ok=True)


def convert_to_dzi(image_path, cleanup=False):
    """CLI-facing wrapper around process_image()."""
    src = Path(image_path).resolve()
    artworks_dir = Path(__file__).parent / "Artworks"

    print(f"Converting {src.name} to DZI...")
    print(f"Slug: {_safe_slug(src.stem)}")

    if not HAS_PYVIPS:
        print("\npyvips not found, falling back to vips CLI (no progress bar)...")

    result = process_image(src, artworks_dir, cleanup=cleanup)

    print(f"\n✓ DZI created at {_safe_path(artworks_dir, result['slug'])}/")
    print("✓ Original kept for crop export")
    print("✓ Thumbnail ready")
    if cleanup:
        print("✓ Source image removed (--cleanup)")

    return result


def _convert_with_pyvips(image_path, dzi_dir, slug):
    image = pyvips.Image.new_from_file(str(image_path), access="sequential")
    image.set_progress(True)
    image.signal_connect("eval", show_progress)

    output = str(dzi_dir / slug)
    image.dzsave(
        output,
        layout="dz",
        tile_size=256,
        overlap=1,
        suffix=".jpg[Q=95]",
    )

    if not (dzi_dir / f"{slug}.dzi").exists():
        raise RuntimeError("dzsave didn't produce a .dzi file")
    if not (dzi_dir / f"{slug}_files").exists():
        raise RuntimeError("dzsave didn't produce a tile directory")


def _convert_with_cli(image_path, dzi_dir, slug):
    subprocess.run(
        [
            "vips", "dzsave", str(image_path), str(dzi_dir / slug),
            "--layout", "dz",
            "--tile-size", "256",
            "--overlap", "1",
            "--suffix", ".jpg[Q=95]",
        ],
        check=True,
    )


def _save_metadata(slug, original_name, dzi_file, artworks_dir):
    metadata_file = artworks_dir / ".artworks.json"

    metadata = {}
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text())
        except Exception:
            pass

    metadata[slug] = {
        "original_name": original_name,
    }

    metadata_file.write_text(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert images to DZI format")
    parser.add_argument("image", help="path to the image")
    parser.add_argument("--cleanup", action="store_true", help="remove original after conversion")
    args = parser.parse_args()

    convert_to_dzi(args.image, cleanup=args.cleanup)

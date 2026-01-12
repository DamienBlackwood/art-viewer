#!/usr/bin/env python3
"""
Optimized thumbnail generation utility.
Generates lightweight thumbnails without blocking - uses lowest zoom tile if available.
"""

import json
from pathlib import Path

try:
    import pyvips
    HAS_PYVIPS = True
except ImportError:
    HAS_PYVIPS = False


def get_or_generate_thumbnail(artwork_slug, artworks_dir, size=200):
    """
    Get or generate thumbnail for artwork. Returns path if exists/created, None if not possible.
    Uses zoom level 0 (smallest) from DZI if available - ultra fast and lightweight.
    """
    artworks_dir = Path(artworks_dir)
    artwork_path = artworks_dir / artwork_slug
    thumb_path = artwork_path / f'.thumb-{size}.jpg'

    # Return if already exists
    if thumb_path.exists():
        return str(thumb_path)

    # Try to use zoom level 0 tile (fastest approach)
    dzi_files = artwork_path / f'{artwork_slug}_files'
    zoom_0_dir = dzi_files / '0'

    if not zoom_0_dir.exists():
        return None

    # Try both .jpg and .jpeg
    zoom_0 = zoom_0_dir / '0_0.jpg'
    if not zoom_0.exists():
        zoom_0 = zoom_0_dir / '0_0.jpeg'
    if not zoom_0.exists():
        return None

    try:
        if HAS_PYVIPS:
            # Just scale the smallest tile - almost instant
            img = pyvips.Image.new_from_file(str(zoom_0))
            scaled = img.resize(size / max(img.width, img.height))
            scaled.write_to_file(str(thumb_path), suffix='.jpg[Q=80]')
        else:
            import subprocess
            subprocess.run([
                'vips', 'resize', str(zoom_0), str(thumb_path),
                str(size / 256)
            ], check=True, capture_output=True)
        return str(thumb_path)
    except:
        pass

    return None


def has_thumbnail(artwork_slug, artworks_dir, size=200):
    """Check if thumbnail exists"""
    thumb_path = Path(artworks_dir) / artwork_slug / f'.thumb-{size}.jpg'
    return thumb_path.exists()


def update_metadata_with_thumbnails(artworks_dir):
    """
    Scan all artworks and generate missing thumbnails.
    Returns dict of {slug: has_thumbnail}
    """
    artworks_dir = Path(artworks_dir)
    metadata_file = artworks_dir / '.artworks.json'

    if not metadata_file.exists():
        return {}

    try:
        metadata = json.loads(metadata_file.read_text())
    except:
        return {}

    results = {}
    for slug in metadata.keys():
        if get_or_generate_thumbnail(slug, artworks_dir):
            results[slug] = True
        else:
            results[slug] = False

    return results

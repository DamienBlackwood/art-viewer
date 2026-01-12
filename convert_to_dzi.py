#!/usr/bin/env python3
"""
Convert images to DZI format for the gallery.
Usage: python3 convert_to_dzi.py image.jpg
       python3 convert_to_dzi.py image.jpg --cleanup
"""

import sys
import json
import re
from pathlib import Path

try:
    import pyvips
    HAS_PYVIPS = True
except ImportError:
    HAS_PYVIPS = False
    import subprocess

from thumb_utils import get_or_generate_thumbnail


def slugify(name):
    slug = re.sub(r'[^\w\s-]', '', name)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.lower().strip('-')


def show_progress(image, progress):
    percent = progress.percent
    bar_length = 40
    filled = int(bar_length * percent / 100)
    bar = '█' * filled + '░' * (bar_length - filled)

    eta_str = f"{progress.eta:.0f}s" if progress.eta > 0 else "calculating..."
    elapsed = progress.run

    print(f'\r[{bar}] {percent:3d}% | {elapsed:.1f}s elapsed | {eta_str} remaining', end='', flush=True)


def convert_to_dzi(image_path, cleanup=False):
    original_image_path = Path(image_path).resolve()

    if not original_image_path.exists():
        print(f"Error: File not found: {original_image_path}")
        sys.exit(1)

    original_name = original_image_path.stem
    clean_slug = slugify(original_name)

    if not clean_slug:
        clean_slug = 'artwork'

    script_dir = Path(__file__).parent
    artworks_dir = script_dir / 'Artworks'
    artworks_dir.mkdir(exist_ok=True)

    image_in_artworks = artworks_dir / original_image_path.name
    print(f"Converting {original_image_path.name} to DZI format...")
    print(f"Slug: {clean_slug}")

    try:
        image_in_artworks.write_bytes(original_image_path.read_bytes())

        dzi_dir = artworks_dir / clean_slug
        dzi_file = dzi_dir / f'{clean_slug}.dzi'
        dzi_dir.mkdir(exist_ok=True)

        if HAS_PYVIPS:
            convert_with_pyvips(image_in_artworks, dzi_dir, clean_slug)
        else:
            print("\npyvips not available, using vips CLI (no progress)...")
            convert_with_cli(image_in_artworks, dzi_dir, clean_slug)

        print(f"\n✓ DZI created successfully!")
        print(f"Files saved to: {dzi_dir}/")

        print("Generating thumbnail...", end=' ', flush=True)
        if get_or_generate_thumbnail(clean_slug, artworks_dir):
            print("✓")
        else:
            print("(skipped)")

        save_artwork_metadata(clean_slug, original_name, dzi_file, artworks_dir)

        image_in_artworks.unlink()
        print(f"✓ Copied image cleaned up")

    except Exception as e:
        print(f"\nError: {e}")
        if image_in_artworks.exists():
            image_in_artworks.unlink()
        sys.exit(1)


def convert_with_pyvips(image_path, dzi_dir, slug):
    image = pyvips.Image.new_from_file(str(image_path), access='sequential')

    image.set_progress(True)
    image.signal_connect('eval', show_progress)

    output_path = str(dzi_dir / slug)

    image.dzsave(
        output_path,
        layout='dz',
        tile_size=256,
        overlap=1,
        suffix='.jpg[Q=85]'
    )

    dzi_file = dzi_dir / f'{slug}.dzi'
    tiles_dir = dzi_dir / f'{slug}_files'

    if not dzi_file.exists():
        raise Exception(f"DZI file not created: {dzi_file}")
    if not tiles_dir.exists():
        raise Exception(f"Tiles directory not created: {tiles_dir}")


def convert_with_cli(image_path, dzi_dir, slug):
    subprocess.run([
        'vips', 'dzsave', str(image_path), str(dzi_dir / slug),
        '--layout', 'dz',
        '--tile-size', '256',
        '--overlap', '1',
        '--suffix', '.jpg[Q=85]'
    ], check=True)


def save_artwork_metadata(slug, original_name, dzi_file, artworks_dir):
    metadata_file = artworks_dir / '.artworks.json'

    metadata = {}
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text())
        except:
            pass

    metadata[slug] = {
        'original_name': original_name,
        'dzi_path': f'{slug}/{slug}.dzi',
        'dzi_file': str(dzi_file)
    }

    metadata_file.write_text(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 convert_to_dzi.py <image.jpg> [--cleanup]")
        print("       --cleanup: Delete original image after conversion")
        sys.exit(1)

    cleanup = '--cleanup' in sys.argv
    image_file = sys.argv[1]
    convert_to_dzi(image_file, cleanup)

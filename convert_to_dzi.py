#!/usr/bin/env python3
"""
Convert JPEG/PNG images to DZI format for OpenSeadragon viewer.
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


def slugify(name):
    """Convert name to URL-safe slug"""
    # Remove special characters, keep only alphanumeric, hyphens, underscores
    slug = re.sub(r'[^\w\s-]', '', name)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.lower().strip('-')


def show_progress(image, progress):
    """Display progress bar"""
    percent = progress.percent
    bar_length = 40
    filled = int(bar_length * percent / 100)
    bar = '█' * filled + '░' * (bar_length - filled)

    eta_str = f"{progress.eta:.0f}s" if progress.eta > 0 else "calculating..."
    elapsed = progress.run

    print(f'\r[{bar}] {percent:3d}% | {elapsed:.1f}s elapsed | {eta_str} remaining', end='', flush=True)


def convert_to_dzi(image_path, cleanup=False):
    """Convert image to DZI format with clean URL-safe paths"""

    image_path = Path(image_path).resolve()

    if not image_path.exists():
        print(f"Error: File not found: {image_path}")
        sys.exit(1)

    # Create clean slug from original filename
    original_name = image_path.stem
    clean_slug = slugify(original_name)

    if not clean_slug:
        clean_slug = 'artwork'

    script_dir = Path(__file__).parent
    dzi_dir = script_dir / clean_slug
    dzi_file = dzi_dir / f'{clean_slug}.dzi'

    print(f"Converting {image_path.name} to DZI format...")
    print(f"Slug: {clean_slug}")

    # Create output directory
    dzi_dir.mkdir(exist_ok=True)

    try:
        if HAS_PYVIPS:
            # Use pyvips with progress tracking
            convert_with_pyvips(image_path, dzi_dir, clean_slug)
        else:
            # Fallback to CLI vips
            print("\npyvips not available, using vips CLI (no progress)...")
            convert_with_cli(image_path, dzi_dir, clean_slug)

        print(f"\n✓ DZI created successfully!")
        print(f"Files saved to: {dzi_dir}/")
        print(f"\nViewer links:")
        print(f"  Direct:    viewer.html?image={clean_slug}/{clean_slug}.dzi")
        print(f"  Gallery:   gallery.html (auto-discovers all artworks)")

        # Store metadata for gallery
        save_artwork_metadata(clean_slug, original_name, dzi_file)

        if cleanup and image_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
            image_path.unlink()
            print(f"✓ Original image deleted")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


def convert_with_pyvips(image_path, dzi_dir, slug):
    """Convert using pyvips with progress tracking"""
    image = pyvips.Image.new_from_file(str(image_path), access='sequential')

    # Enable progress reporting
    image.set_progress(True)
    image.signal_connect('eval', show_progress)

    # vips dzsave creates: slug.dzi and slug_files/
    # We want them in dzi_dir
    output_path = str(dzi_dir / slug)

    # Save as DZI with progress - use 'dz' layout for Deep Zoom
    image.dzsave(
        output_path,
        layout='dz',
        tile_size=256,
        overlap=1,
        suffix='.jpg[Q=85]'
    )

    # Verify the files were created
    dzi_file = dzi_dir / f'{slug}.dzi'
    tiles_dir = dzi_dir / f'{slug}_files'

    if not dzi_file.exists():
        raise Exception(f"DZI file not created: {dzi_file}")
    if not tiles_dir.exists():
        raise Exception(f"Tiles directory not created: {tiles_dir}")


def convert_with_cli(image_path, dzi_dir, slug):
    """Fallback to vips CLI without progress"""
    subprocess.run([
        'vips', 'dzsave', str(image_path), str(dzi_dir / slug),
        '--layout', 'dz',
        '--tile-size', '256',
        '--overlap', '1',
        '--suffix', '.jpg[Q=85]'
    ], check=True)


def save_artwork_metadata(slug, original_name, dzi_file):
    """Save metadata about converted artwork"""
    script_dir = Path(__file__).parent
    metadata_file = script_dir / '.artworks.json'

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

# Art Viewing

An elegant deep zoom art gallery with integrated viewer. Convert any JPEG/PNG to explore artwork in stunning detail.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# (Optional) Install pyvips for progress tracking during conversion
# pip install pyvips
```

## Quick Start

```bash
# 1. Start the gallery
python3 serve.py

# 2. Open browser
# Visit: http://localhost:8000
```

You'll see a beautiful dark-themed gallery with:
- **Sidebar** - All your artworks listed
- **Viewer** - Click any artwork to explore with deep zoom
- **Controls** - Fullscreen, toggle sidebar, keyboard shortcuts

## Add New Artwork

```bash
# Convert an image
python3 convert_to_dzi.py "My Artwork.jpg"

# Refresh browser - new artwork appears in gallery!
```

## Features

### Integrated Gallery + Viewer
- **Sidebar gallery** - Browse all artworks at a glance
- **Integrated viewer** - Click to explore in deep zoom
- **Auto-discovery** - No configuration needed
- **Clean UI** - Dark theme, minimal distractions
- **Keyboard shortcuts**:
  - `ESC` - Toggle sidebar
  - `F` - Fullscreen

### Smart Conversion
- **Auto-slugification** - "My Art.jpg" → "my-art"
- **Progress tracking** - Real-time progress bar for large files
- **Optimized output** - JPEG tiles, perfect quality/size balance
- **Original cleanup** - Optional `--cleanup` flag

## Adding Artwork

```bash
# Convert any image
python3 convert_to_dzi.py "Vincent van Gogh - Starry Night.jpg"

# Refresh browser - artwork appears automatically
```

The script:
1. Creates clean URL-safe slug: `vincent-van-gogh-starry-night`
2. Generates DZI tiles with proper Deep Zoom layout
3. Saves metadata for gallery discovery
4. Shows real-time progress with ETA

### Advanced Options

```bash
# Delete original after conversion
python3 convert_to_dzi.py image.jpg --cleanup

# Install pyvips for progress tracking
pip3 install pyvips
```

## How It Works

**The Gallery (`index.html`)**

When you visit `http://localhost:8000`, you see:
- **Left sidebar** - Gallery of all artworks
- **Main area** - Deep zoom viewer
- **Top right** - Controls (gallery toggle, fullscreen)

Click any artwork in the sidebar → it loads instantly in the viewer with full zoom capability.

**The Server (`serve.py`)**
- Serves `index.html` at the root
- API endpoint `/api/artworks` auto-discovers all DZI files
- Returns artwork metadata (name, path, slug)

**The Converter (`convert_to_dzi.py`)**
- Takes any JPEG/PNG
- Creates Deep Zoom tiles (256x256 JPEG, Q85)
- Auto-generates clean URL-safe names
- Saves metadata for gallery discovery

## Project Structure

```
gallery/
├── index.html                  # Gallery app
├── serve.py                    # Server + API
├── convert_to_dzi.py           # Image converter
├── requirements.txt
├── README.md
│
└── Artworks/
    ├── mona-lisa/
    │   ├── mona-lisa.dzi
    │   └── mona-lisa_files/
    │       ├── 0/, 1/, 2/, ...
    │
    └── starry-night/
        ├── starry-night.dzi
        └── starry-night_files/
```

## Viewer Controls

- **Mouse wheel** - Zoom in/out
- **Click & drag** - Pan around
- **Double-click** - Zoom to point
- **ESC** - Toggle gallery sidebar
- **F** - Toggle fullscreen

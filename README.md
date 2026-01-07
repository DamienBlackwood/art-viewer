# Art Viewer

View massive gigapixel images without overloading your RAM!

## Quick Start

```bash
git clone https://github.com/DamienBlackwood/art-viewer.git
python3 serve.py
# Visit http://localhost:8000
```

## Add Artwork

```bash
python3 convert_to_dzi.py "image.jpg"
```

That's it. Refresh browser and it appears.

## Features

- **Deep Zoom** - Smooth zoom on massive images
- **Gallery + Viewer** - Browse sidebar, click to explore
- **Auto-discovery** - Drop converted images, they just work
- **Keyboard**: `ESC` (toggle sidebar), `F` (fullscreen)
- **Smart conversion** - Auto-slugifies filenames, tracks progress

## Controls

| Action | Key/Gesture |
|--------|-------------|
| Zoom | Mouse wheel / pinch |
| Pan | Click & drag |
| Fullscreen | F |
| Toggle sidebar | ESC |

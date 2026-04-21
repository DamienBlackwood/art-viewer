# art viewer
I made this so I could view gigapixel art without destroying my laptop.

## installing

```bash
git clone https://github.com/DamienBlackwood/art-viewer.git

python3 serve.py

# then visit http://localhost:8000
```

## adding artworks

```bash
python3 convert_to_dzi.py "image.jpg"
```

now just refresh your browser and it'll appear

## features

- **deep zoom** - smooth zoom on massive images
- **gallery + viewer** - the ability to browse converted artworks ***(work in progress)***
- **auto-discovery** - automatically display art dropped into the repository
- **smart conversion** - auto-slugifies filenames, tracks progress and other jazz

## controls

| action | key/gesture |
|--------|-------------|
| zoom | mouse wheel / pinch |
| pan | click & drag |
| fullscreen | F |
| toggle sidebar | ESC |

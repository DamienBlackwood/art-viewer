# Changelog

## v2.5.0
- Interactive compare mode with artwork selection picker
- Colour picker tool with hex/rgb readout and copy functionality
- Client-side crop selection with pixel-accurate export
- Custom confirm modals and error toast styling
- Unified OpenSeadragon configuration across all viewers
- Fixed artwork deletion to properly clean up folders on macOS
- Extracted JavaScript to separate file for cleaner HTML
- Added version indicator badge

## v0.2.0
- Redesigned the UI to match my portfolio somewhat
- Cleaned up the conversion script
- Improved the border glow implementation (took a few tries)
- Added cursor polish

## v0.1.5
- Artworks folder is now created automatically if it doesn't exist
- Moved `.artworks.json` inside `Artworks/` to keep things tidy
- Updated all paths accordingly

## v0.1.0
- Initial release
- Deep zoom viewer via OpenSeadragon
- Local Python server for tile serving
- DZI conversion script with pyvips support
- Auto-discovery of artworks from the Artworks folder

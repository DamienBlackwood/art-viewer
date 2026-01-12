#!/usr/bin/env python3
"""
my smart server that handles DZI file serving with correct paths.
Fixes the issue where OpenSeadragon can't find tile files.
"""

import json
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

from thumb_utils import get_or_generate_thumbnail

class SmartDZIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # get all artworks
        if path == '/api/artworks':
            self.send_artworks()
            return

        # get thumbnail (lazy gen if needed)
        if path.startswith('/api/thumb/'):
            slug = path.replace('/api/thumb/', '')
            self.send_thumbnail(slug)
            return

        if path == '/':
            self.path = '/index.html'

        super().do_GET()

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # check if thumbnail exists
        if path.startswith('/api/thumb/'):
            slug = path.replace('/api/thumb/', '')
            script_dir = Path(__file__).parent
            artworks_dir = script_dir / 'Artworks'
            thumb_path = get_or_generate_thumbnail(slug, artworks_dir)

            if thumb_path and Path(thumb_path).exists():
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.send_header('Content-Length', str(Path(thumb_path).stat().st_size))
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
            return

        super().do_HEAD()

    def send_artworks(self):
        """Scan and return all available artworks"""
        artworks = []
        script_dir = Path(__file__).parent
        artworks_dir = script_dir / 'Artworks'

        if not artworks_dir.exists():
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps([]).encode())
            return

        # Look for directories containing .dzi files in Artworks folder
        for item in sorted(artworks_dir.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith('.'):
                continue

            dzi_file = item / f'{item.name}.dzi'
            if dzi_file.exists():
                # Load metadata if possible
                metadata_file = artworks_dir / '.artworks.json'
                original_name = item.name

                if metadata_file.exists():
                    try:
                        metadata = json.loads(metadata_file.read_text())
                        if item.name in metadata:
                            original_name = metadata[item.name].get('original_name', item.name)
                    except:
                        pass

                artworks.append({
                    'name': original_name,
                    'slug': item.name,
                    'path': f'Artworks/{item.name}/{item.name}.dzi',
                    'thumbnail': f'/api/thumb/{item.name}'
                })

        # Send a JSON response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(artworks, indent=2).encode())

    def send_thumbnail(self, slug):
        # gen if doesn't exist
        script_dir = Path(__file__).parent
        artworks_dir = script_dir / 'Artworks'
        thumb_path = get_or_generate_thumbnail(slug, artworks_dir)

        if thumb_path and Path(thumb_path).exists():
            # serve the file
            self.send_response(200)
            self.send_header('Content-type', 'image/jpeg')
            self.send_header('Cache-Control', 'public, max-age=31536000')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(thumb_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            # no thumbnail available, return 404
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'thumbnail not available'}).encode())

    def end_headers(self):
        """Add CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        super().end_headers()

if __name__ == '__main__':
    PORT = 8000
    Handler = SmartDZIHandler

    os.chdir(Path(__file__).parent)

    with HTTPServer(("", PORT), Handler) as httpd:
        print(f"Art Gallery Server")
        print(f"====================")
        print(f"")
        print(f"Gallery: http://localhost:{PORT}")
        print(f"")
        print(f"Press Ctrl+C to stop")
        print(f"")
        print(f"Thank you!")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped")

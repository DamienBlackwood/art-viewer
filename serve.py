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

class SmartDZIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # API endpoint: get all artworks
        if path == '/api/artworks':
            self.send_artworks()
            return

        if path == '/':
            self.path = '/index.html'

        super().do_GET()

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
                    'thumbnail': '🖼️'
                })

        # Send a JSON response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(artworks, indent=2).encode())

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

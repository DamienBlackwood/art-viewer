#!/usr/bin/env python3
"""
Art Gallery Server — hardened, minimal, serves DZI tiles and handles
curatorial operations: annotations, crop export, upload conversion.
"""

import io
import json
import os
import re
import tempfile
import time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

from thumb_utils import get_or_generate_thumbnail
from convert_to_dzi import process_image

PORT = 8000
MAX_UPLOAD = 5 * 1024 * 1024 * 1024  # it's currently 5GB, but this can be customized.
UPLOAD_COOLDOWN = 2.0


def _extract_boundary(content_type):
    m = re.search(r'boundary=([^;\s]+)', content_type)
    if not m:
        return None
    return m.group(1).strip('"\'').encode()


def _parse_multipart(body, boundary):
    parts = {}
    delimiter = b'--' + boundary
    segments = body.split(delimiter)
    for chunk in segments[1:-1]:
        chunk = chunk.lstrip(b'\r\n')
        if chunk.startswith(b'--'):
            continue
        if not chunk:
            continue
        head, _, data = chunk.partition(b'\r\n\r\n')
        if not head:
            continue
        if data.endswith(b'\r\n'):
            data = data[:-2]
        disp = re.search(
            rb'Content-Disposition:\s*form-data;\s*name=(?:(?:"([^"]*)")|(?:\'([^\']*)\')|([^;\s]+))',
            head, re.IGNORECASE
        )
        if disp:
            name = (disp.group(1) or disp.group(2) or disp.group(3) or b'').decode()
            fname = re.search(
                rb'(?:^|;\s*)filename=(?:(?:"([^"]*)")|(?:\'([^\']*)\')|([^;\s]+))',
                head, re.IGNORECASE
            )
            filename = (fname.group(1) or fname.group(2) or fname.group(3) or b'').decode() if fname else None
            parts[name] = (filename, data)
    return parts


def _sanitize_filename(filename):
    if not filename:
        return None
    filename = filename.replace('\\', '/')
    filename = Path(filename).name
    filename = re.sub(r'[\x00-\x1f]', '', filename)
    if filename in ('', '.', '..'):
        return None
    return filename


def _is_image(data):
    if len(data) < 12:
        return False
    if data[:3] == b'\xff\xd8\xff':
        return True
    if data[:4] == b'\x89PNG':
        return True
    if data[:4] == b'GIF8':
        return True
    if data[:2] == b'BM':
        return True
    if data[:4] in (b'II\x2a\x00', b'MM\x00\x2a'):
        return True
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return True
    return False


def _safe_path(base_dir, *parts):
    base = Path(base_dir).resolve()
    target = base.joinpath(*parts).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise RuntimeError("path traversal blocked")
    return target


class SmartDZIHandler(SimpleHTTPRequestHandler):
    _last_upload = 0.0

    def version_string(self):
        return "art-viewer"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == '/api/artworks':
            self.send_artworks()
            return
        if path.startswith('/api/thumb/'):
            slug = path.replace('/api/thumb/', '')
            self.send_thumbnail(slug)
            return
        if path.startswith('/api/annotations/'):
            slug = path.replace('/api/annotations/', '')
            self.send_annotations(slug)
            return
        if path == '/':
            self.path = '/index.html'

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == '/api/convert':
            self.handle_convert()
            return
        if path.startswith('/api/annotations/'):
            slug = path.replace('/api/annotations/', '')
            self.handle_save_annotations(slug)
            return
        if path.startswith('/api/crop/'):
            slug = path.replace('/api/crop/', '')
            self.handle_crop(slug)
            return

        self.send_json({"error": "not found"}, status=404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path.startswith('/api/artworks/'):
            slug = path.replace('/api/artworks/', '')
            self.handle_delete_artwork(slug)
            return

        self.send_json({"error": "not found"}, status=404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def handle_convert(self):
        content_type = self.headers.get('Content-Type', '')
        if not content_type.startswith('multipart/form-data'):
            self.send_json({"error": "expected multipart/form-data"}, status=400)
            return

        try:
            length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            self.send_json({"error": "bad Content-Length"}, status=400)
            return

        if length > MAX_UPLOAD:
            self.send_json({"error": "file too large (max 5GB)"}, status=413)
            return

        now = time.time()
        if now - SmartDZIHandler._last_upload < UPLOAD_COOLDOWN:
            self.send_json({"error": "please wait before uploading again"}, status=429)
            return
        SmartDZIHandler._last_upload = now

        boundary = _extract_boundary(content_type)
        if not boundary:
            self.send_json({"error": "missing boundary"}, status=400)
            return

        body = self.rfile.read(length)
        parts = _parse_multipart(body, boundary)

        if 'image' not in parts:
            self.send_json({"error": "no image field"}, status=400)
            return

        raw_filename, data = parts['image']
        filename = _sanitize_filename(raw_filename)
        if not filename or not data:
            self.send_json({"error": "no file provided"}, status=400)
            return

        if not _is_image(data):
            self.send_json({"error": "file does not look like an image"}, status=400)
            return

        suffix = Path(filename).suffix
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            artworks_dir = Path(__file__).parent / 'Artworks'
            # derive a clean name from the original filename
            original_name = Path(filename).stem
            result = process_image(tmp_path, artworks_dir, original_name=original_name)
            self.send_json(result, status=200)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    def send_annotations(self, slug):
        try:
            ann_file = _safe_path(Path(__file__).parent / 'Artworks', slug, 'annotations.json')
            if ann_file.exists():
                self.send_json(json.loads(ann_file.read_text()))
            else:
                self.send_json({"salt": None, "annotations": []})
        except Exception:
            self.send_json({"error": "invalid slug"}, status=400)

    def handle_save_annotations(self, slug):
        try:
            length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            self.send_json({"error": "bad length"}, status=400)
            return

        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self.send_json({"error": "invalid json"}, status=400)
            return

        try:
            ann_file = _safe_path(Path(__file__).parent / 'Artworks', slug, 'annotations.json')
            ann_file.write_text(json.dumps(data, indent=2))
            self.send_json({"ok": True})
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_crop(self, slug):
        try:
            length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            self.send_json({"error": "bad length"}, status=400)
            return

        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except Exception:
            self.send_json({"error": "invalid json"}, status=400)
            return

        x = int(req.get('x', 0))
        y = int(req.get('y', 0))
        w = int(req.get('width', 0))
        h = int(req.get('height', 0))
        if w <= 0 or h <= 0:
            self.send_json({"error": "invalid dimensions"}, status=400)
            return

        try:
            artwork_dir = _safe_path(Path(__file__).parent / 'Artworks', slug)
            original = None
            for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp']:
                candidate = artwork_dir / f'original{ext}'
                if candidate.exists():
                    original = candidate
                    break

            if not original:
                self.send_json({"error": "original image not found"}, status=404)
                return

            try:
                import pyvips
                img = pyvips.Image.new_from_file(str(original))
                crop = img.crop(x, y, w, h)
                buf = crop.write_to_buffer('.jpg[Q=92]')
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(buf)))
                self.end_headers()
                self.wfile.write(buf)
                return
            except ImportError:
                self.send_json({"error": "pyvips required for crop"}, status=501)
                return
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_delete_artwork(self, slug):
        try:
            artwork_dir = _safe_path(Path(__file__).parent / 'Artworks', slug)
            if not artwork_dir.exists():
                self.send_json({"error": "artwork not found"}, status=404)
                return

            import shutil
            shutil.rmtree(str(artwork_dir), ignore_errors=True)

            artworks_dir = Path(__file__).parent / 'Artworks'
            metadata_file = artworks_dir / '.artworks.json'
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text())
                    if slug in metadata:
                        del metadata[slug]
                        metadata_file.write_text(json.dumps(metadata, indent=2))
                except Exception:
                    pass

            self.send_json({"ok": True})
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path.startswith('/api/thumb/'):
            slug = path.replace('/api/thumb/', '')
            artworks_dir = Path(__file__).parent / 'Artworks'
            thumb_path = get_or_generate_thumbnail(slug, artworks_dir)

            if thumb_path and Path(thumb_path).exists():
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(Path(thumb_path).stat().st_size))
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
            return

        super().do_HEAD()

    def send_artworks(self):
        artworks = []
        script_dir = Path(__file__).parent
        artworks_dir = script_dir / 'Artworks'

        if not artworks_dir.exists():
            self.send_json([])
            return

        metadata_file = artworks_dir / '.artworks.json'
        metadata = {}
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
            except Exception:
                pass

        for item in sorted(artworks_dir.iterdir()):
            if not item.is_dir() or item.name.startswith('.'):
                continue

            dzi_file = item / f'{item.name}.dzi'
            if not dzi_file.exists():
                continue

            original_name = metadata.get(item.name, {}).get('original_name', item.name)

            ann_count = 0
            ann_file = item / 'annotations.json'
            if ann_file.exists():
                try:
                    ann_data = json.loads(ann_file.read_text())
                    ann_count = len(ann_data.get('annotations', []))
                except Exception:
                    pass

            artworks.append({
                'name': original_name,
                'slug': item.name,
                'path': f'Artworks/{item.name}/{item.name}.dzi',
                'thumbnail': f'/api/thumb/{item.name}',
                'annotations': ann_count
            })

        self.send_json(artworks)

    def send_thumbnail(self, slug):
        artworks_dir = Path(__file__).parent / 'Artworks'
        thumb_path = get_or_generate_thumbnail(slug, artworks_dir)

        if thumb_path and Path(thumb_path).exists():
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'public, max-age=31536000')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(thumb_path, 'rb') as f:
                self.wfile.write(f.read())
            return

        self.send_json({'error': 'thumbnail not found'}, status=404)

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            self.wfile.write(json.dumps(data, indent=2).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        super().end_headers()


if __name__ == '__main__':
    os.chdir(Path(__file__).parent)

    print("Art Gallery Server")
    print("=" * 20)
    print()
    print(f"Gallery: http://localhost:{PORT}")
    print("Binding: 127.0.0.1 only")
    print()
    print("Press Ctrl+C to stop")
    print()

    with HTTPServer(("127.0.0.1", PORT), SmartDZIHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")

"""Standard-library HTTP API. Loopback-only by design."""
import argparse
import hmac
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import Store, ValidationError, HOST_RE

MAX_BODY = 8192
WEB = Path(__file__).with_name('web')


def handler_factory(store, ingest_key, read_key):
    if not ingest_key or not read_key or ingest_key == read_key:
        raise ValueError('set distinct non-empty ingestion and reader tokens')

    class Handler(BaseHTTPRequestHandler):
        server_version = 'Sentinel/0.1'
        def _send(self, code, obj):
            data = json.dumps(obj, separators=(',', ':')).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'")
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self, role):
            expected = ingest_key if role == 'ingest' else read_key
            header = self.headers.get('Authorization', '')
            return hmac.compare_digest(header, 'Bearer ' + expected)

        def _require(self, role):
            if not self._authorized(role):
                self._send(401, {'error':'unauthorized'})
                return False
            return True

        def _path(self):
            return urllib.parse.urlsplit(self.path)

        def do_GET(self):
            parsed = self._path()
            if parsed.path == '/healthz':
                self._send(200, {'status':'ok'})
                return
            if parsed.path in ('/', '/app.js'):
                filename = 'index.html' if parsed.path == '/' else 'app.js'
                data = (WEB / filename).read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8' if filename.endswith('html') else 'text/javascript; charset=utf-8')
                self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Cache-Control','no-store')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path not in ('/api/events','/api/alerts','/api/stats'):
                self._send(404, {'error':'not found'})
                return
            if not self._require('read'):
                return
            q = urllib.parse.parse_qs(parsed.query)
            try:
                limit = int(q.get('limit',['50'])[0])
                if not 1 <= limit <= 200:
                    raise ValueError
            except (ValueError, TypeError):
                self._send(400, {'error':'invalid limit'})
                return
            if parsed.path == '/api/events':
                host = q.get('host',[None])[0]
                if host is not None and not HOST_RE.fullmatch(host):
                    self._send(400, {'error':'invalid host'})
                    return
                self._send(200, {'events':store.events(limit, host)})
            elif parsed.path == '/api/alerts':
                self._send(200, {'alerts':store.alerts(limit)})
            else:
                self._send(200, store.stats())

        def do_POST(self):
            path = self._path().path
            if path == '/api/events':
                if not self._require('ingest'):
                    return
            elif path.startswith('/api/alerts/') and path.endswith('/ack'):
                if not self._require('read'):
                    return
            else:
                self._send(404, {'error':'not found'})
                return
            if path != '/api/events':
                try:
                    alert_id = int(path.split('/')[3])
                    if alert_id < 1:
                        raise ValueError
                except (ValueError, IndexError):
                    self._send(400, {'error':'invalid alert id'})
                    return
                updated = store.acknowledge(alert_id)
                self._send(200 if updated else 404, {'acknowledged':updated})
                return
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 1 <= length <= MAX_BODY:
                    self._send(413, {'error':'body size invalid'})
                    return
                if self.headers.get('Content-Type','').split(';')[0].strip() != 'application/json':
                    self._send(415, {'error':'expected application/json'})
                    return
                raw = json.loads(self.rfile.read(length))
                inserted, detections = store.ingest(raw)
                self._send(201 if inserted else 200, {'inserted':inserted,'detections':detections})
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                self._send(400, {'error':str(exc)})

        def log_message(self, format, *args):
            # Avoid logging credentials, paths, or untrusted payloads.
            return

    return Handler


def make_server(host, port, db_path, ingest_key, read_key):
    if host not in ('127.0.0.1', '::1', 'localhost') and not (host == '0.0.0.0' and os.environ.get('SENTINEL_CONTAINER_BIND') == '1'):
        raise ValueError('Sentinel MVP is loopback-only; use a TLS/authenticated reverse proxy in future releases')
    store = Store(db_path)
    server = ThreadingHTTPServer((host, port), handler_factory(store, ingest_key, read_key))
    server.daemon_threads = True
    server.store = store
    return server


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--db', default='sentinel.sqlite3')
    args = p.parse_args()
    server = make_server(args.host, args.port, args.db, os.environ.get('SENTINEL_INGEST_TOKEN'), os.environ.get('SENTINEL_READ_TOKEN'))
    try:
        print(f'Sentinel listening on http://{args.host}:{server.server_port}')
        server.serve_forever()
    finally:
        server.server_close()
        server.store.close()

if __name__ == '__main__':
    main()

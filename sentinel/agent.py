"""Send JSONL events to an authorized Sentinel loopback server."""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.error
import urllib.request


def validate_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or not parsed.port):
        raise ValueError('destination must be a loopback HTTP URL with an explicit port')
    return url.rstrip('/')


def send_lines(stream, url, token):
    url = validate_url(url)
    successes = 0
    for lineno, line in enumerate(stream, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            payload = json.dumps(event).encode('utf-8')
            request = urllib.request.Request(url.rstrip('/') + '/api/events', payload,
                {'Authorization':'Bearer '+token, 'Content-Type':'application/json'}, method='POST')
            with urllib.request.urlopen(request, timeout=5) as response:
                result = json.load(response)
            print(f"line {lineno}: {'inserted' if result['inserted'] else 'duplicate'} detections={result['detections']}")
            successes += 1
        except (json.JSONDecodeError, urllib.error.URLError, ValueError, KeyError) as exc:
            print(f'line {lineno}: rejected ({type(exc).__name__})', file=sys.stderr)
    return successes


def main():
    p = argparse.ArgumentParser()
    p.add_argument('file', help='JSONL file or - for stdin')
    p.add_argument('--url', default='http://127.0.0.1:8765')
    args = p.parse_args()
    try:
        validate_url(args.url)
    except ValueError as exc:
        p.error(str(exc))
    token = os.environ.get('SENTINEL_INGEST_TOKEN')
    if not token:
        p.error('SENTINEL_INGEST_TOKEN required')
    stream = sys.stdin if args.file == '-' else open(args.file, encoding='utf-8')
    try:
        count = send_lines(stream, args.url, token)
    finally:
        if stream is not sys.stdin:
            stream.close()
    if count == 0:
        raise SystemExit(1)

if __name__ == '__main__':
    main()

"""Agent isolation, credential rotation and schema migration regression tests."""
import datetime as dt
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from sentinel.api import make_server
from sentinel.core import Store, ValidationError
from sentinel.credentials import IngestCredentials, parse_agent_tokens

KEY1 = 'A' * 40
KEY2 = 'B' * 40
KEY3 = 'C' * 40


def event(n, host='node-1'):
    return {'id': f'agent_{n:08d}', 'host': host, 'kind': 'host_up',
            'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(), 'detail': 'healthy'}


class CredentialsTests(unittest.TestCase):
    def test_rotation_and_identity(self):
        agents = parse_agent_tokens(json.dumps({'node-1': [KEY1, KEY2], 'node-2': KEY3}), 'legacy_key', 'reader_key')
        credentials = IngestCredentials('legacy_key', 'reader_key', agents)
        self.assertEqual(credentials.identify('Bearer ' + KEY1), 'node-1')
        self.assertEqual(credentials.identify('Bearer ' + KEY2), 'node-1')
        self.assertEqual(credentials.identify('Bearer ' + KEY3), 'node-2')
        self.assertEqual(credentials.identify('Bearer legacy_key'), 'legacy')
        for value in ('Bearer reader_key', 'Bearer invalid', 'Basic '+KEY1, '', 'Bearer '+KEY1+'x'):
            self.assertIsNone(credentials.identify(value))
        rotated = parse_agent_tokens(json.dumps({'node-1': [KEY2, KEY3]}), None, 'reader_key')
        updated = IngestCredentials(None, 'reader_key', rotated)
        self.assertIsNone(updated.identify('Bearer ' + KEY1))
        self.assertEqual(updated.identify('Bearer ' + KEY2), 'node-1')

    def test_reject_unsafe_configuration(self):
        bad = ['[]', '{', json.dumps({'bad host': KEY1}),
               json.dumps({'legacy': KEY1}), json.dumps({'node-1': 'short'}),
               json.dumps({'node-1': [KEY1] * 2}),
               json.dumps({'node-1': KEY1, 'node-2': KEY1}),
               json.dumps({'node-1': [KEY1, KEY2, KEY3, 'D'*40]}),
               json.dumps({'node-1': KEY1, 'node-2': 'reader_key'})]
        for config in bad:
            with self.subTest(config=config), self.assertRaises(ValueError):
                parse_agent_tokens(config, 'legacy_key', 'reader_key')
        with self.assertRaises(ValueError):
            parse_agent_tokens(json.dumps({'node-1': KEY1}), KEY1, 'reader_key')
        with self.assertRaises(ValueError):
            parse_agent_tokens(json.dumps({'node-1': KEY1}), None, KEY1)
        with self.assertRaises(ValueError):
            IngestCredentials(None, 'reader_key', {})

    def test_store_agent_attribution_and_cross_agent_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'events.sqlite3')
            try:
                first = event(1)
                self.assertEqual(store.ingest(first, agent_id='node-1'), (True, []))
                self.assertEqual(store.events()[0]['agent_id'], 'node-1')
                self.assertEqual(store.ingest(first, agent_id='node-1'), (False, []))
                with self.assertRaises(ValidationError):
                    store.ingest(first, agent_id='legacy')
                with self.assertRaises(ValidationError):
                    store.ingest(event(2, host='node-2'), agent_id='node-1')
                self.assertEqual(store.stats()['events'], 1)
            finally:
                store.close()

    def test_legacy_schema_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / 'old.sqlite3'
            conn = sqlite3.connect(filename)
            conn.execute('CREATE TABLE events(id TEXT PRIMARY KEY,host TEXT,kind TEXT,timestamp TEXT,detail TEXT)')
            old = event(1)
            conn.execute('INSERT INTO events VALUES(?,?,?,?,?)',
                         (old['id'], old['host'], old['kind'], old['timestamp'], old['detail']))
            conn.commit()
            conn.close()
            store = Store(filename)
            try:
                self.assertEqual(store.events()[0]['agent_id'], 'legacy')
                self.assertEqual(store.ingest(old), (False, []))
                self.assertEqual(store.ingest(event(2), agent_id='node-1'), (True, []))
            finally:
                store.close()

    def test_http_agent_scope_and_reader_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            server = make_server('127.0.0.1', 0, Path(directory)/'db.sqlite3', None,
                                 'reader_key', agent_tokens={'node-1': (KEY1, KEY2), 'node-2': (KEY3,)})
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            def request(path, token, payload=None):
                data = json.dumps(payload).encode() if payload is not None else None
                req = urllib.request.Request(url + path, data=data,
                      headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'},
                      method='POST' if payload is not None else 'GET')
                try:
                    with urllib.request.urlopen(req, timeout=4) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as exc:
                    return exc.code, json.load(exc)
            try:
                first = event(1)
                self.assertEqual(request('/api/events', KEY1, first)[0], 201)
                self.assertEqual(request('/api/events', KEY2, first)[0], 200)
                self.assertEqual(request('/api/events', KEY3, event(2, 'node-2'))[0], 201)
                self.assertEqual(request('/api/events', KEY1, event(3, 'node-2'))[0], 403)
                self.assertEqual(request('/api/events', 'reader_key', event(4))[0], 401)
                self.assertEqual(request('/api/events', KEY1)[0], 401)
                status, body = request('/api/events', 'reader_key')
                self.assertEqual(status, 200)
                self.assertEqual({x['agent_id'] for x in body['events']}, {'node-1', 'node-2'})
                self.assertEqual(request('/api/stats', 'reader_key')[1]['events'], 2)
            finally:
                server.shutdown()
                server.server_close()
                server.store.close()


if __name__ == '__main__':
    unittest.main()

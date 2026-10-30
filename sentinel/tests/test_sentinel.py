import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import json
import io
from unittest.mock import patch
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from sentinel.api import TokenBucket, make_server
from sentinel.agent import send_lines, validate_url
from sentinel.core import Store, ValidationError, parse_event

NOW = dt.datetime.now(dt.timezone.utc)
def event(n, kind='auth_failure', host='node-1', when=None, detail='test'):
    return {'id':f'evt_{n:08d}','kind':kind,'host':host,'timestamp':(when or NOW).isoformat(),'detail':detail}

class AgentTests(unittest.TestCase):
    def test_url_guard(self):
        self.assertEqual(validate_url('http://127.0.0.1:8765'), 'http://127.0.0.1:8765')
        for url in ('http://127.0.0.1:8765@evil.com', 'http://example.com:8765',
                    'https://127.0.0.1:8765', 'http://127.0.0.1:8765/evil',
                    'http://127.0.0.1:8765/?foo=1'):
            with self.subTest(url=url), self.assertRaises(ValueError): validate_url(url)

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name)/'events.db')
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def test_schema_and_time(self):
        for changed in ({'host':'bad host'}, {'kind':'evil'}, {'kind':[]}, {'timestamp':'2020-01-01T00:00:00Z'}, {'detail':'x'*513}, {'id':'a'}, {'timestamp':'2026-10-01'}, {'extra':1}):
            with self.subTest(changed=changed),self.assertRaises(ValidationError):
                parse_event({**event(1), **changed})
    def test_idempotence_and_collision(self):
        self.assertEqual(self.store.ingest(event(1)), (True, []))
        self.assertEqual(self.store.ingest(event(1)), (False, []))
        with self.assertRaises(ValidationError): self.store.ingest(event(1, detail='changed'))
        self.assertEqual(self.store.stats()['events'],1)
    def test_burst_detection(self):
        for i in range(4):
            self.assertEqual(self.store.ingest(event(i)), (True, []))
        self.assertEqual(self.store.ingest(event(4)), (True, ['auth_burst']))
        self.assertEqual(self.store.stats()['alerts'],1)
        self.assertEqual(self.store.ingest(event(4)), (False, []))
        self.assertEqual(self.store.stats()['alerts'],1)
    def test_late_event_completes_burst(self):
        base = NOW - dt.timedelta(minutes=30)
        # Arrival order is intentionally different from event-time order.
        for i in (0, 1, 3, 4):
            inserted, detections = self.store.ingest(event(100+i, when=base+dt.timedelta(minutes=i)))
            self.assertTrue(inserted)
            self.assertEqual(detections, [])
        inserted, detections = self.store.ingest(event(102, when=base+dt.timedelta(minutes=2)))
        self.assertEqual((inserted, detections), (True, ['auth_burst']))
        self.assertEqual(self.store.stats()['alerts'], 1)
        alert = self.store.alerts()[0]
        self.assertEqual(alert['event_id'], 'evt_00000104')
        self.assertEqual(alert['timestamp'], (base+dt.timedelta(minutes=4)).isoformat())

    def test_late_earliest_event_does_not_duplicate_alert(self):
        base = NOW - dt.timedelta(minutes=30)
        for i in (1, 2, 3, 4, 5):
            self.store.ingest(event(200+i, when=base+dt.timedelta(minutes=i)))
        self.assertEqual(self.store.stats()['alerts'], 1)
        self.assertEqual(self.store.ingest(event(200, when=base)), (True, []))
        self.assertEqual(self.store.stats()['alerts'], 1)

    def test_late_event_does_not_create_false_burst(self):
        base = NOW - dt.timedelta(minutes=30)
        for i, minutes in enumerate((0, 1, 2, 6, 7)):
            self.store.ingest(event(300+i, when=base+dt.timedelta(minutes=minutes)))
        self.assertEqual(self.store.stats()['alerts'], 0)

    def test_separated_auth_bursts(self):
        base = NOW - dt.timedelta(minutes=40)
        for i in range(5):
            self.store.ingest(event(400+i, when=base+dt.timedelta(seconds=30*i)))
        for i in range(5):
            self.store.ingest(event(500+i, when=base+dt.timedelta(minutes=15, seconds=30*i)))
        self.assertEqual(self.store.stats()['alerts'], 2)

    def test_auth_burst_window_includes_exact_five_minute_boundary(self):
        base = NOW - dt.timedelta(minutes=30)
        for i in range(5):
            self.store.ingest(event(600+i, when=base+dt.timedelta(seconds=75*i)))
        self.assertEqual(self.store.stats()['alerts'], 1)

    def test_isolated_hosts(self):
        for i in range(4): self.store.ingest(event(i,host='a'))
        self.store.ingest(event(5,host='b'))
        self.assertEqual(self.store.stats()['alerts'],0)
        self.assertEqual(len(self.store.events(host='b')),1)
    def test_direct_alerts_ack(self):
        self.store.ingest(event(1,'host_down'))
        self.store.ingest(event(2,'integrity_changed'))
        self.assertEqual(self.store.stats()['unacknowledged'],2)
        aid=self.store.alerts()[0]['id']
        self.assertTrue(self.store.acknowledge(aid))
        self.assertFalse(self.store.acknowledge(aid))
        self.assertEqual(self.store.stats()['unacknowledged'],1)
        audit = self.store.audit()
        self.assertEqual(len(audit),1)
        self.assertEqual(audit[0]['alert_id'],aid)
        self.assertEqual(audit[0]['action'],'acknowledged')
        self.assertEqual(audit[0]['actor'],'reader_token')
    def test_audit_persistence_and_no_duplicate(self):
        self.store.ingest(event(77,'host_down'))
        alert_id = self.store.alerts()[0]['id']
        self.assertTrue(self.store.acknowledge(alert_id))
        self.assertFalse(self.store.acknowledge(alert_id))
        self.assertFalse(self.store.acknowledge(999999))
        other = Store(Path(self.tmp.name)/'events.db')
        try:
            rows = other.audit()
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['alert_id'],alert_id)
            self.assertEqual(len(other.audit(limit=1)),1)
        finally:
            other.close()

    def test_concurrent_ack_has_single_audit_record(self):
        self.store.ingest(event(88, 'host_down'))
        alert_id = self.store.alerts()[0]['id']
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(self.store.acknowledge, [alert_id] * 16))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(len(self.store.audit()), 1)
        self.assertEqual(self.store.stats()['unacknowledged'], 0)

    def test_persistence(self):
        self.store.ingest(event(1,'host_down'))
        other=Store(Path(self.tmp.name)/'events.db')
        try: self.assertEqual(other.stats()['alerts'],1)
        finally: other.close()
    def test_event_ordering(self):
        self.store.ingest(event(1, when=NOW-dt.timedelta(minutes=2)))
        self.store.ingest(event(2, when=NOW-dt.timedelta(minutes=1)))
        self.assertEqual(self.store.events(limit=1)[0]['id'],'evt_00000002')

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.server=make_server('127.0.0.1',0,Path(cls.tmp.name)/'db.sqlite3','ingest_secret','reader_secret')
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.server.store.close();cls.tmp.cleanup()
    def req(self, path, token=None, body=None, content_type='application/json'):
        headers={}
        if token:headers['Authorization']='Bearer '+token
        if body is not None:headers['Content-Type']=content_type
        request=urllib.request.Request(self.url+path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method='POST' if body is not None else 'GET')
        try:
            with urllib.request.urlopen(request,timeout=4) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
    def test_auth_and_roles(self):
        self.assertEqual(self.req('/api/events')[0],401)
        self.assertEqual(self.req('/api/events','ingest_secret')[0],401)
        self.assertEqual(self.req('/api/events','reader_secret')[0],200)
        self.assertEqual(self.req('/api/audit')[0],401)
        self.assertEqual(self.req('/api/audit','ingest_secret')[0],401)
        self.assertEqual(self.req('/api/audit','reader_secret')[0],200)
        self.assertEqual(self.req('/api/events','reader_secret',event(11))[0],401)
        self.assertEqual(self.req('/api/events','ingest_secret',event(11))[0],201)
        self.assertEqual(self.req('/api/events','ingest_secret',event(11))[0],200)
    def test_limits_and_errors(self):
        self.assertEqual(self.req('/api/events?limit=201','reader_secret')[0],400)
        self.assertEqual(self.req('/api/audit?limit=201','reader_secret')[0],400)
        self.assertEqual(self.req('/api/events?host=bad%20host','reader_secret')[0],400)
        self.assertEqual(self.req('/api/events','ingest_secret',{'foo':'bar'})[0],400)
        self.assertEqual(self.req('/api/events','ingest_secret',event(12),'text/plain')[0],415)
        self.assertEqual(self.req('/unknown')[0],404)
    def test_ack_api(self):
        self.req('/api/events','ingest_secret',event(31,'host_down'))
        code, data=self.req('/api/alerts','reader_secret')
        self.assertEqual(code,200)
        alert_id=data['alerts'][0]['id']
        request=urllib.request.Request(self.url+f'/api/alerts/{alert_id}/ack',data=b'',headers={'Authorization':'Bearer reader_secret'},method='POST')
        with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response),{'acknowledged':True})
        with self.assertRaises(urllib.error.HTTPError) as ctx:urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code,404)
        status, data = self.req('/api/audit','reader_secret')
        self.assertEqual(status,200)
        self.assertEqual(len(data['audit']),1)
        self.assertEqual(data['audit'][0]['alert_id'],alert_id)
    def test_loopback_enforced(self):
        with self.assertRaises(ValueError):make_server('0.0.0.0',0,':memory:','i','r')

if __name__=='__main__': unittest.main()


class IngestRateLimitTests(unittest.TestCase):
    def test_bucket_refills_deterministically(self):
        now = [100.0]
        bucket = TokenBucket(burst=2, per_minute=60, clock=lambda: now[0])
        self.assertEqual(bucket.consume(), 0)
        self.assertEqual(bucket.consume(), 0)
        self.assertEqual(bucket.consume(), 1)
        now[0] += 1
        self.assertEqual(bucket.consume(), 0)
        self.assertEqual(bucket.consume(), 1)
        for invalid in (0, -1, 100001, 1.5, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                TokenBucket(burst=invalid)

    def test_ingestion_429_does_not_block_read_api(self):
        with tempfile.TemporaryDirectory() as d:
            server = make_server('127.0.0.1', 0, Path(d)/'rate.db', 'ingest_secret',
                                 'reader_secret', ingest_burst=2, ingest_per_minute=1)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                for i in range(3):
                    payload = json.dumps(event(8000+i)).encode()
                    request = urllib.request.Request(url+'/api/events', data=payload,
                        headers={'Authorization':'Bearer ingest_secret', 'Content-Type':'application/json'},
                        method='POST')
                    try:
                        with urllib.request.urlopen(request, timeout=4) as response:
                            self.assertEqual(response.status, 201)
                            self.assertLess(i, 2)
                    except urllib.error.HTTPError as exc:
                        self.assertEqual(i, 2)
                        self.assertEqual(exc.code, 429)
                        self.assertGreaterEqual(int(exc.headers['Retry-After']), 1)
                        self.assertEqual(json.load(exc)['error'], 'ingest rate limit exceeded')
                read = urllib.request.Request(url+'/api/stats',
                    headers={'Authorization':'Bearer reader_secret'})
                with urllib.request.urlopen(read, timeout=4) as response:
                    self.assertEqual(json.load(response)['events'], 2)
            finally:
                server.shutdown()
                server.server_close()
                server.store.close()


class AgentRetryTests(unittest.TestCase):
    def test_retries_429_with_retry_after(self):
        error = urllib.error.HTTPError('http://127.0.0.1:8765/api/events', 429,
                                      'rate limited', {'Retry-After':'2'}, None)
        response = io.BytesIO(b'{"inserted":true,"detections":[]}')
        with patch('sentinel.agent.urllib.request.urlopen', side_effect=[error, response]) as urlopen:
            delays = []
            result = send_lines(io.StringIO(json.dumps(event(9100))+'\n'),
                                'http://127.0.0.1:8765', 'ingest_secret', sleep=delays.append)
        self.assertEqual(result, 1)
        self.assertEqual(delays, [2])
        self.assertEqual(urlopen.call_count, 2)

    def test_exhausted_retries_report_failure(self):
        def limited(*args, **kwargs):
            raise urllib.error.HTTPError('http://127.0.0.1:8765/api/events', 429,
                                         'rate limited', {'Retry-After':'1'}, None)
        failures = []
        with patch('sentinel.agent.urllib.request.urlopen', side_effect=limited) as urlopen:
            self.assertEqual(send_lines(io.StringIO(json.dumps(event(9101))+'\n'),
                'http://127.0.0.1:8765', 'ingest_secret', sleep=lambda _:None,
                max_retries=2, failures=failures), 0)
        self.assertEqual(failures, [1])
        self.assertEqual(urlopen.call_count, 3)

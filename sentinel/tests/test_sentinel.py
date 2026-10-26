import datetime as dt
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from sentinel.api import make_server
from sentinel.agent import validate_url
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

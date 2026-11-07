import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path
from sentinel.retention import prune_events

NOW = dt.datetime(2026, 11, 7, tzinfo=dt.timezone.utc)

class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'sentinel.db'
        with sqlite3.connect(self.db) as conn:
            conn.executescript('CREATE TABLE events(id TEXT PRIMARY KEY, timestamp TEXT NOT NULL); CREATE TABLE alerts(id INTEGER PRIMARY KEY, event_id TEXT); CREATE TABLE audit_entries(id INTEGER PRIMARY KEY, alert_id INTEGER);')
            for id, age in [('old', 90), ('boundary', 30), ('recent', 1)]:
                conn.execute('INSERT INTO events VALUES (?,?)', (id, (NOW-dt.timedelta(days=age)).isoformat()))
            conn.execute("INSERT INTO alerts VALUES (1,'old')")
            conn.execute('INSERT INTO audit_entries VALUES (1,1)')
    def tearDown(self):
        self.tmp.cleanup()
    def test_dry_run_does_not_delete(self):
        self.assertEqual(prune_events(self.db, days=30, now=NOW)['eligible'], 1)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM events').fetchone()[0], 3)
    def test_apply_preserves_alerts_and_audit(self):
        result = prune_events(self.db, days=30, now=NOW, batch_size=1, dry_run=False)
        self.assertEqual(result['deleted'], 1)
        with sqlite3.connect(self.db) as c:
            self.assertEqual([r[0] for r in c.execute('SELECT id FROM events ORDER BY id')], ['boundary', 'recent'])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM alerts').fetchone()[0], 1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM audit_entries').fetchone()[0], 1)
    def test_invalid_parameters(self):
        for days in [0, -1, 3651, True, 1.5]:
            with self.assertRaises(ValueError):
                prune_events(self.db, days=days)
        with self.assertRaises(ValueError):
            prune_events(self.db, days=30, batch_size=0)
        with self.assertRaises(ValueError):
            prune_events(self.db, days=30, now=NOW.replace(tzinfo=None))
    def test_missing_db_not_created(self):
        missing = Path(self.tmp.name)/'missing.db'
        with self.assertRaises(sqlite3.OperationalError):
            prune_events(missing, days=30)
        self.assertFalse(missing.exists())
    def test_repeat_is_idempotent(self):
        prune_events(self.db, days=30, now=NOW, dry_run=False)
        self.assertEqual(prune_events(self.db, days=30, now=NOW, dry_run=False)['deleted'], 0)

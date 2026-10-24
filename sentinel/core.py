"""Bounded, idempotent SQLite ingestion and deterministic detection rules."""
import datetime as dt
import re
import sqlite3
import threading
from pathlib import Path

KINDS = {'auth_failure', 'auth_success', 'host_down', 'host_up', 'integrity_changed'}
HOST_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
MAX_AGE = dt.timedelta(days=7)
FUTURE_SKEW = dt.timedelta(minutes=5)

class ValidationError(ValueError):
    pass


def parse_event(obj, now=None):
    if not isinstance(obj, dict) or set(obj) != {'id', 'host', 'kind', 'timestamp', 'detail'}:
        raise ValidationError('event must contain exactly id, host, kind, timestamp, detail')
    if not isinstance(obj['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', obj['id']):
        raise ValidationError('invalid id')
    if not isinstance(obj['host'], str) or not HOST_RE.fullmatch(obj['host']):
        raise ValidationError('invalid host')
    if not isinstance(obj['kind'], str) or obj['kind'] not in KINDS:
        raise ValidationError('invalid kind')
    if not isinstance(obj['detail'], str) or len(obj['detail']) > 512:
        raise ValidationError('detail too long')
    try:
        timestamp = dt.datetime.fromisoformat(obj['timestamp'].replace('Z', '+00:00'))
    except (ValueError, AttributeError, TypeError):
        raise ValidationError('invalid timestamp') from None
    if timestamp.tzinfo is None:
        raise ValidationError('timestamp must include timezone')
    now = now or dt.datetime.now(dt.timezone.utc)
    timestamp = timestamp.astimezone(dt.timezone.utc)
    if timestamp < now - MAX_AGE or timestamp > now + FUTURE_SKEW:
        raise ValidationError('timestamp outside accepted window')
    return {**obj, 'timestamp': timestamp.isoformat()}


class Store:
    def __init__(self, filename):
        self.filename = str(filename)
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.filename, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY, host TEXT NOT NULL, kind TEXT NOT NULL,
              timestamp TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_events_host_kind ON events(host,kind,timestamp);
            CREATE TABLE IF NOT EXISTS alerts (
              id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL,
              host TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL,
              timestamp TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0,
              UNIQUE(event_id,kind));
            CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp DESC);
        ''')

    def ingest(self, raw):
        event = parse_event(raw)
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                row = self.db.execute('SELECT * FROM events WHERE id=?', (event['id'],)).fetchone()
                if row:
                    if dict(row) != event:
                        raise ValidationError('id already used for a different event')
                    self.db.execute('COMMIT')
                    return False, []
                self.db.execute('INSERT INTO events(id,host,kind,timestamp,detail) VALUES (:id,:host,:kind,:timestamp,:detail)', event)
                detections = []
                if event['kind'] in ('host_down', 'integrity_changed'):
                    detections.append((event['kind'], 'Host unavailable' if event['kind']=='host_down' else 'File integrity changed'))
                if event['kind'] == 'auth_failure':
                    t = dt.datetime.fromisoformat(event['timestamp']) - dt.timedelta(minutes=5)
                    count = self.db.execute('''SELECT COUNT(*) FROM events WHERE host=? AND kind='auth_failure'
                        AND timestamp>=? AND timestamp<=?''', (event['host'], t.isoformat(), event['timestamp'])).fetchone()[0]
                    if count == 5:
                        detections.append(('auth_burst', 'Five authentication failures within five minutes'))
                for kind, message in detections:
                    self.db.execute('INSERT INTO alerts(event_id,host,kind,message,timestamp) VALUES (?,?,?,?,?)',
                                    (event['id'], event['host'], kind, message, event['timestamp']))
                self.db.execute('COMMIT')
                return True, [kind for kind, _ in detections]
            except Exception:
                self.db.execute('ROLLBACK')
                raise

    def events(self, limit=50, host=None):
        with self.lock:
            if host:
                rows = self.db.execute('SELECT * FROM events WHERE host=? ORDER BY timestamp DESC,id DESC LIMIT ?', (host, limit))
            else:
                rows = self.db.execute('SELECT * FROM events ORDER BY timestamp DESC,id DESC LIMIT ?', (limit,))
            return [dict(r) for r in rows.fetchall()]

    def alerts(self, limit=50):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT * FROM alerts ORDER BY timestamp DESC,id DESC LIMIT ?', (limit,)).fetchall()]

    def acknowledge(self, alert_id):
        with self.lock:
            cur = self.db.execute('UPDATE alerts SET acknowledged=1 WHERE id=? AND acknowledged=0', (alert_id,))
            return cur.rowcount == 1

    def stats(self):
        with self.lock:
            return {'events': self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                    'alerts': self.db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0],
                    'unacknowledged': self.db.execute('SELECT COUNT(*) FROM alerts WHERE acknowledged=0').fetchone()[0],
                    'hosts': self.db.execute('SELECT COUNT(DISTINCT host) FROM events').fetchone()[0]}

    def close(self):
        self.db.close()

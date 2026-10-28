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
        self.db.execute('PRAGMA foreign_keys=ON')
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
            CREATE TABLE IF NOT EXISTS audit_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              alert_id INTEGER NOT NULL,
              action TEXT NOT NULL CHECK(action = 'acknowledged'),
              actor TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              FOREIGN KEY(alert_id) REFERENCES alerts(id));
            CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_entries(timestamp DESC,id DESC);
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
                    # Search event-time windows on BOTH sides of a late arrival.
                    # A late failure may be the first, middle, or last of the five.
                    # Restrict the query to a 10-minute neighborhood, not the full history.
                    when = dt.datetime.fromisoformat(event['timestamp'])
                    window = dt.timedelta(minutes=5)
                    rows = self.db.execute('''SELECT id,timestamp FROM events
                        WHERE host=? AND kind='auth_failure' AND timestamp>=? AND timestamp<=?
                        ORDER BY timestamp,id''',
                        (event['host'], (when-window).isoformat(), (when+window).isoformat())).fetchall()
                    for i in range(4, len(rows)):
                        group = rows[i-4:i+1]
                        if event['id'] not in (r['id'] for r in group):
                            continue
                        end = dt.datetime.fromisoformat(group[-1]['timestamp'])
                        start = dt.datetime.fromisoformat(group[0]['timestamp'])
                        if end-start > window:
                            continue
                        # Suppress duplicate alerts from the same burst, including
                        # an earlier trigger discovered after an alert was emitted.
                        prior = self.db.execute('''SELECT 1 FROM alerts
                            WHERE host=? AND kind='auth_burst' AND timestamp>=? AND timestamp<=?
                            LIMIT 1''', (event['host'], (end-window).isoformat(),
                                          (end+window).isoformat())).fetchone()
                        if not prior:
                            self.db.execute('''INSERT INTO alerts(event_id,host,kind,message,timestamp)
                                VALUES (?,?,?,?,?)''',
                                (group[-1]['id'], event['host'], 'auth_burst',
                                 'Five authentication failures within five minutes', end.isoformat()))
                            detections.append(('auth_burst', 'Five authentication failures within five minutes'))
                        break
                for kind, message in detections:
                    if kind == 'auth_burst':
                        continue  # inserted above with its event-time anchor
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
        """Acknowledge exactly once and atomically preserve an audit record.

        The MVP has a shared reader token rather than per-user identities, so the
        actor is deliberately a role label, not a fabricated user identity.
        """
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                cur = self.db.execute('UPDATE alerts SET acknowledged=1 WHERE id=? AND acknowledged=0', (alert_id,))
                updated = cur.rowcount == 1
                if updated:
                    self.db.execute("""INSERT INTO audit_entries(alert_id,action,actor,timestamp)
                        VALUES (?,?,?,?)""", (alert_id, 'acknowledged', 'reader_token',
                        dt.datetime.now(dt.timezone.utc).isoformat()))
                self.db.execute('COMMIT')
                return updated
            except Exception:
                self.db.execute('ROLLBACK')
                raise

    def audit(self, limit=50):
        with self.lock:
            rows = self.db.execute("""SELECT id,alert_id,action,actor,timestamp FROM audit_entries
                ORDER BY timestamp DESC,id DESC LIMIT ?""", (limit,))
            return [dict(r) for r in rows.fetchall()]

    def stats(self):
        with self.lock:
            return {'events': self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                    'alerts': self.db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0],
                    'unacknowledged': self.db.execute('SELECT COUNT(*) FROM alerts WHERE acknowledged=0').fetchone()[0],
                    'hosts': self.db.execute('SELECT COUNT(DISTINCT host) FROM events').fetchone()[0]}

    def close(self):
        self.db.close()

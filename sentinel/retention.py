"""Explicit bounded retention for Sentinel raw events; alerts and audit are preserved."""
import argparse
import datetime as dt
import sqlite3
from pathlib import Path

def prune_events(db_path, *, days, now=None, batch_size=500, dry_run=True):
    if type(days) is not int or not 1 <= days <= 3650:
        raise ValueError('days must be an integer between 1 and 3650')
    if type(batch_size) is not int or not 1 <= batch_size <= 10000:
        raise ValueError('batch_size must be an integer between 1 and 10000')
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must have timezone')
    cutoff = (now.astimezone(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    uri = Path(db_path).resolve().as_uri() + '?mode=rw'
    with sqlite3.connect(uri, uri=True, timeout=10) as db:
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('BEGIN IMMEDIATE' if not dry_run else 'BEGIN')
        try:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='events'").fetchone():
                raise ValueError('not a Sentinel event database')
            count = db.execute('SELECT COUNT(*) FROM events WHERE timestamp < ?', (cutoff,)).fetchone()[0]
            if not dry_run:
                while True:
                    ids = db.execute('SELECT id FROM events WHERE timestamp < ? ORDER BY timestamp,id LIMIT ?', (cutoff, batch_size)).fetchall()
                    if not ids:
                        break
                    db.executemany('DELETE FROM events WHERE id=?', ids)
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {'eligible': count, 'deleted': 0 if dry_run else count, 'cutoff': cutoff, 'dry_run': dry_run}

def main():
    p = argparse.ArgumentParser(description='Prune Sentinel raw events; preserve alerts and audit')
    p.add_argument('--db', required=True)
    p.add_argument('--days', type=int, required=True)
    p.add_argument('--batch-size', type=int, default=500)
    p.add_argument('--apply', action='store_true', help='delete; default is dry run')
    args = p.parse_args()
    print(prune_events(args.db, days=args.days, batch_size=args.batch_size, dry_run=not args.apply))

if __name__ == '__main__':
    main()

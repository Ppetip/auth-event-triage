"""Correlate failed logins and subsequent success using event-time sliding windows, producing evidence for a SOC analyst."""
from collections import defaultdict, deque
from datetime import datetime

def analyze(data):
    window = int(data.get('window_seconds', 300))
    threshold = int(data.get('threshold', 5))
    if window < 1 or threshold < 2:
        raise ValueError('window must be positive; threshold at least two')
    events = []
    for index, event in enumerate(data['events']):
        stamp = datetime.fromisoformat(event['time'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('timestamps must include a timezone')
        if event['outcome'] not in ('failure', 'success'):
            raise ValueError('unknown outcome')
        events.append((stamp.timestamp(), index, event))
    windows = defaultdict(deque)
    findings = []
    for stamp, index, event in sorted(events):
        key = (event['source'], event['user'])
        queue = windows[key]
        while queue and stamp - queue[0][0] > window:
            queue.popleft()
        if event['outcome'] == 'failure':
            queue.append((stamp, index))
            if len(queue) == threshold:
                findings.append(dict(kind='failure_burst', source=key[0], user=key[1], evidence=[x[1] for x in queue]))
        else:
            if len(queue) >= threshold:
                findings.append(dict(kind='success_after_burst', source=key[0], user=key[1], evidence=[x[1] for x in queue]+[index]))
            queue.clear()
    return findings


def main():
    import argparse, json, sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='path to JSON input, or - for stdin')
    args = parser.parse_args()
    try:
        if args.input == '-':
            data = json.load(sys.stdin)
        else:
            with open(args.input, encoding='utf-8') as stream:
                data = json.load(stream)
        result = analyze(data)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        print('Invalid input: '+str(error), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())

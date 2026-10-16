"""Normalize timestamped evidence into a UTC timeline, deduplicate stable IDs and detect contradictory records."""
from datetime import datetime,timezone

def analyze(data):
    seen = {}
    result = []
    for record in data['records']:
        stamp = datetime.fromisoformat(record['time'].replace('Z','+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('timezone required')
        normalized = dict(record,time=stamp.astimezone(timezone.utc).isoformat())
        key = (record['source'],record['id'])
        if key in seen:
            if normalized!=seen[key]:
                raise ValueError('conflicting evidence ID')
            continue
        seen[key]=normalized
        result.append(dict(kind='event',**normalized))
    return sorted(result,key=lambda x:(x['time'],x['source'],str(x['id'])))


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

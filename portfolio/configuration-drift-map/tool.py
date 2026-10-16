"""Compare nested configuration snapshots using JSON Pointer paths with auditable exact-path ignores."""
def escape(value):
    return value.replace('~','~0').replace('/','~1')

def analyze(data):
    result = []
    ignored = set(data.get('ignore_paths',[]))
    def walk(before,after,path):
        if path in ignored:
            return
        if type(before) is not type(after):
            result.append(dict(kind='changed',path=path,before=before,after=after)); return
        if isinstance(before,dict):
            for key in sorted(before.keys() | after.keys()):
                child = path+'/'+escape(key)
                if child in ignored:
                    continue
                if key not in before:
                    result.append(dict(kind='added',path=child,after=after[key]))
                elif key not in after:
                    result.append(dict(kind='removed',path=child,before=before[key]))
                else:
                    walk(before[key],after[key],child)
        elif before!=after:
            result.append(dict(kind='changed',path=path,before=before,after=after))
    walk(data['before'],data['after'],'')
    return result


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

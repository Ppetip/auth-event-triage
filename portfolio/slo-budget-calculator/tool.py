"""Compute request-based error-budget consumption and burn rates for explicitly bounded observation windows."""
import math

def analyze(data):
    target = float(data['target'])
    if not math.isfinite(target) or not 0<target<1:
        raise ValueError('target must be between zero and one, exclusive')
    result = []
    for sample in data['windows']:
        total,bad = sample['total'],sample['bad']
        if isinstance(total,bool) or isinstance(bad,bool) or not isinstance(total,int) or not isinstance(bad,int) or not 0<=bad<=total:
            raise ValueError('counts must be integers with 0 <= bad <= total')
        allowed = total*(1-target)
        burn = bad/allowed if total else None
        result.append(dict(kind='no_data' if not total else 'over_budget' if burn>1+1e-12 else 'within_budget',name=sample['name'],total=total,bad=bad,allowed_bad=allowed,remaining_bad=allowed-bad,burn_rate=burn,availability=1-bad/total if total else None))
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

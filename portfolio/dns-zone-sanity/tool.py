"""Lint normalized DNS exports for CNAME collisions, malformed IP records and SPF policy mistakes without sending queries."""
import ipaddress
from collections import defaultdict

def analyze(data):
    groups=defaultdict(list)
    findings=[]
    for record in data['records']:
        name=record['name'].rstrip('.').lower()
        kind=record['type'].upper()
        value=record['value']
        groups[name].append((kind,value))
        if kind in ('A','AAAA'):
            try:
                address=ipaddress.ip_address(value)
                if address.version != (4 if kind=='A' else 6):
                    raise ValueError('address family mismatch')
            except ValueError:
                findings.append(dict(kind='invalid_address',name=name,type=kind))
        if int(record.get('ttl',3600))<0:
            raise ValueError('negative TTL')
    for name,records in sorted(groups.items()):
        types=[r[0] for r in records]
        if 'CNAME' in types and (len(types)>1):
            findings.append(dict(kind='cname_collision',name=name))
        spf=[v for t,v in records if t=='TXT' and v.lower().startswith('v=spf1')]
        if len(spf)>1:
            findings.append(dict(kind='multiple_spf',name=name))
        for value in spf:
            terms=value.split()[1:]
            if any(term.lower() in ('+all','all') for term in terms):
                findings.append(dict(kind='spf_allow_all',name=name))
            if sum(term.lower().lstrip('+~-?').startswith(('include:','a:','mx:','exists:','redirect=')) or term.lower().lstrip('+~-?') in ('a','mx','ptr') for term in terms)>10:
                findings.append(dict(kind='spf_lookup_floor',name=name))
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

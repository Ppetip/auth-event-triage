import unittest
import tool

class BehaviorTests(unittest.TestCase):
    def test_case_0(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'events': []})], [])

    def test_case_1(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'threshold': 2, 'events': [{'time': '2026-01-01T00:00:00Z', 'source': 'a', 'user': 'u', 'outcome': 'failure'}, {'time': '2026-01-01T00:00:01Z', 'source': 'a', 'user': 'u', 'outcome': 'failure'}, {'time': '2026-01-01T00:00:02Z', 'source': 'a', 'user': 'u', 'outcome': 'success'}]})], ['failure_burst', 'success_after_burst'])

    def test_case_2(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'threshold': 2, 'events': [{'time': '2026-01-01T00:00:00Z', 'source': 'a', 'user': 'u', 'outcome': 'failure'}, {'time': '2026-01-01T00:06:01Z', 'source': 'a', 'user': 'u', 'outcome': 'failure'}]})], [])

    def test_missing_required_input(self):
        with self.assertRaises((KeyError, ValueError, TypeError)):
            tool.analyze({})


    def test_sources_do_not_cross_correlate(self):
        events=[dict(time='2026-01-01T00:00:00Z',user='u',source=s,outcome='failure') for s in ('a','b')]
        self.assertEqual(tool.analyze(dict(threshold=2,events=events)),[])
    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            tool.analyze({'events':[dict(time='2026-01-01',user='u',source='a',outcome='failure')]})
    def test_event_time_sorting_preserves_evidence_indexes(self):
        events=[dict(time=t,source='a',user='u',outcome=o) for t,o in [('2026-01-01T00:00:02Z','success'),('2026-01-01T00:00:00Z','failure'),('2026-01-01T00:00:01Z','failure')]]
        self.assertEqual(tool.analyze(dict(threshold=2,events=events))[-1]['evidence'],[1,2,0])

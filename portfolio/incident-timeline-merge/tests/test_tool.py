import unittest
import tool

class BehaviorTests(unittest.TestCase):
    def test_case_0(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'records': []})], [])

    def test_case_1(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'records': [{'source': 'a', 'id': '1', 'time': '2026-01-01T01:00:00+01:00', 'message': 'demo'}]})], ['event'])

    def test_case_2(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'records': [{'source': 'a', 'id': '1', 'time': '2026-01-01T00:00:00Z'}, {'source': 'a', 'id': '1', 'time': '2026-01-01T00:00:00Z'}]})], ['event'])

    def test_missing_required_input(self):
        with self.assertRaises((KeyError, ValueError, TypeError)):
            tool.analyze({})


    def test_conflicting_id_rejected(self):
        a={'source':'a','id':'1','time':'2026-01-01T00:00:00Z','message':'one'}
        with self.assertRaises(ValueError): tool.analyze({'records':[a,dict(a,message='two')]})
    def test_offsets_ordered_in_utc(self):
        result=tool.analyze({'records':[{'source':'a','id':'1','time':'2026-01-01T00:00:00-05:00'},{'source':'a','id':'2','time':'2026-01-01T01:00:00Z'}]})
        self.assertEqual([x['id'] for x in result],['2','1'])

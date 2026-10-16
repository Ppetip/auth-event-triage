import unittest
import tool

class BehaviorTests(unittest.TestCase):
    def test_case_0(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'records': []})], [])

    def test_case_1(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'records': [{'name': 'x', 'type': 'A', 'value': '::1'}]})], ['invalid_address'])

    def test_case_2(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'records': [{'name': 'X.', 'type': 'CNAME', 'value': 'y.'}, {'name': 'x', 'type': 'A', 'value': '192.0.2.1'}]})], ['cname_collision'])

    def test_missing_required_input(self):
        with self.assertRaises((KeyError, ValueError, TypeError)):
            tool.analyze({})


    def test_spf_duplicates_case_insensitive_name(self):
        result=tool.analyze({'records':[{'name':'X.','type':'TXT','value':'v=spf1 -all'},{'name':'x','type':'TXT','value':'v=spf1 ~all'}]})
        self.assertEqual(result,[{'kind':'multiple_spf','name':'x'}])
    def test_spf_lookup_floor(self):
        result=tool.analyze({'records':[{'name':'x','type':'TXT','value':'v=spf1 '+' '.join('include:x'+str(i) for i in range(11))}]})
        self.assertEqual(result[0]['kind'],'spf_lookup_floor')
    def test_negative_ttl_rejected(self):
        with self.assertRaises(ValueError): tool.analyze({'records':[{'name':'x','type':'A','value':'192.0.2.1','ttl':-1}]})

import unittest
import tool

class BehaviorTests(unittest.TestCase):
    def test_case_0(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'before': {}, 'after': {}})], [])

    def test_case_1(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'before': {'a/b': 1}, 'after': {'a/b': 2}})], ['changed'])

    def test_case_2(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'before': {'x': 1}, 'after': {'x': 2}, 'ignore_paths': ['/x']})], [])

    def test_missing_required_input(self):
        with self.assertRaises((KeyError, ValueError, TypeError)):
            tool.analyze({})


    def test_json_pointer_escaping(self):
        self.assertEqual(tool.analyze({'before':{'a/~b':1},'after':{'a/~b':2}})[0]['path'],'/a~1~0b')
    def test_null_not_confused_with_missing(self):
        self.assertEqual(tool.analyze({'before':{'x':None},'after':{}}),[{'kind':'removed','path':'/x','before':None}])
    def test_boolean_and_integer_are_distinct(self):
        self.assertEqual(len(tool.analyze({'before':{'x':True},'after':{'x':1}})),1)

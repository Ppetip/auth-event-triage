import unittest
import tool

class BehaviorTests(unittest.TestCase):
    def test_case_0(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'target': 0.99, 'windows': []})], [])

    def test_case_1(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'target': 0.99, 'windows': [{'name': 'h', 'total': 1000, 'bad': 20}]})], ['over_budget'])

    def test_case_2(self):
        self.assertEqual([x["kind"] for x in tool.analyze({'target': 0.99, 'windows': [{'name': 'h', 'total': 0, 'bad': 0}]})], ['no_data'])

    def test_missing_required_input(self):
        with self.assertRaises((KeyError, ValueError, TypeError)):
            tool.analyze({})


    def test_exact_budget_boundary(self):
        result=tool.analyze({'target':.99,'windows':[{'name':'x','total':1000,'bad':10}]})[0]
        self.assertEqual(result['kind'],'within_budget')
        self.assertAlmostEqual(result['burn_rate'],1)
    def test_invalid_counts(self):
        for bad in (-1,101,1.5,True):
            with self.subTest(bad=bad), self.assertRaises(ValueError): tool.analyze({'target':.99,'windows':[{'name':'x','total':100,'bad':bad}]})
    def test_nan_target_rejected(self):
        with self.assertRaises(ValueError): tool.analyze({'target':float('nan'),'windows':[]})

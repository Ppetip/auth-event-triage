import json
import os
from pathlib import Path
import unittest
import tool

class ContractTests(unittest.TestCase):
    def test_rejects_unknown_action(self):
        with self.assertRaises(ValueError): tool.validate({'steps':[{'action':'evaluate','name':'x'}]})
    def test_rejects_unnamed_action(self):
        with self.assertRaises(ValueError): tool.validate({'steps':[{'action':'click','name':''}]})
    def test_step_limit(self):
        with self.assertRaises(ValueError): tool.validate({'steps':[{'action':'click','name':'x'}]*51})
    def test_empty_contract(self):
        self.assertEqual(tool.validate({'steps':[]}),[])
    def test_missing_fill_value(self):
        with self.assertRaises(ValueError): tool.validate({'steps':[{'action':'fill','name':'x'}]})
    @unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS')=='1','opt-in browser integration test')
    def test_demo_actions_and_assertions(self):
        result=tool.run(Path('demo.html').read_text(),json.loads(Path('contract.json').read_text()))
        self.assertEqual(len(result),7)
        self.assertTrue(all(x['kind']=='passed' for x in result))
    @unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS')=='1','opt-in browser integration test')
    def test_missing_button_fails_and_stops(self):
        result=tool.run('<button>Present</button>',{'steps':[{'action':'click','name':'Missing'},{'action':'click','name':'Present'}]})
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['kind'],'failed')

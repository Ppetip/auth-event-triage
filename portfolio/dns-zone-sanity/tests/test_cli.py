import json
from pathlib import Path
import subprocess
import sys
import unittest

class CLITests(unittest.TestCase):
    def test_example_is_runnable_json(self):
        result=subprocess.run([sys.executable,'tool.py','example.json'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIsInstance(json.loads(result.stdout),list)
    def test_invalid_json_returns_two_without_traceback(self):
        result=subprocess.run([sys.executable,'tool.py','-'],input='{bad',capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertNotIn('Traceback',result.stderr)
    def test_stdin_matches_file(self):
        result=subprocess.run([sys.executable,'tool.py','-'],input=Path('example.json').read_text(),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        file_result=subprocess.run([sys.executable,'tool.py','example.json'],capture_output=True,text=True)
        self.assertEqual(json.loads(result.stdout),json.loads(file_result.stdout))

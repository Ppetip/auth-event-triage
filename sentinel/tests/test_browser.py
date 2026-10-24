"""Real Chromium smoke test, run explicitly with: python -m unittest sentinel.tests.test_browser -v."""
import tempfile
import shutil
import threading
import unittest
from pathlib import Path
from sentinel.api import make_server
from sentinel.core import Store
from .test_sentinel import event

class BrowserTests(unittest.TestCase):
    def test_ui_buttons_and_safe_rendering(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright not installed')
        with tempfile.TemporaryDirectory() as d:
            server=make_server('127.0.0.1',0,Path(d)/'db.sqlite3','ingest_secret','reader_secret')
            server.store.ingest(event(41,'host_down',detail='<img src=x onerror=alert(1)>'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with sync_playwright() as p:
                    browser=p.chromium.launch(headless=True, **({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}))
                    try:
                        page=browser.new_page()
                        page.goto(f'http://127.0.0.1:{server.server_port}/')
                        page.get_by_label('Reader token').fill('reader_secret')
                        page.get_by_role('button',name='Connect').click()
                        page.get_by_text('Updated successfully.').wait_for()
                        self.assertEqual(page.locator('#alerts-total').inner_text(),'1')
                        self.assertEqual(page.locator('img').count(),0)
                        self.assertIn('<img src=x onerror=alert(1)>',page.locator('#events-body').inner_text())
                        page.get_by_role('button',name='Acknowledge alert 1 on node-1').click()
                        page.get_by_text('Updated successfully.').wait_for()
                        self.assertEqual(page.locator('#open-total').inner_text(),'0')
                        page.get_by_label('Host filter').fill('no-such-host')
                        page.get_by_role('button',name='Apply filter').click()
                        self.assertIn('No events',page.locator('#events-body').inner_text())
                        page.get_by_role('button',name='Refresh').click()
                        self.assertEqual(page.locator('#events-total').inner_text(),'1')
                        self.assertEqual(page.locator('html').get_attribute('lang'),'en')
                    finally:browser.close()
            finally:
                server.shutdown();server.server_close();server.store.close()

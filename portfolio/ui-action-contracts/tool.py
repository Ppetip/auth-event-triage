"""Verify explicit UI contracts against disposable HTML with network blocked."""
import argparse
import json
from pathlib import Path

def validate(contract):
    steps=contract['steps']
    if not isinstance(steps,list) or len(steps)>50:
        raise ValueError('steps must be a list of at most 50 actions')
    for step in steps:
        if step['action'] not in ('click','fill','check','text'):
            raise ValueError('unsupported action')
        if not isinstance(step.get('name'),str) or not step['name']:
            raise ValueError('each action needs an accessible name')
        if step['action']=='fill' and not isinstance(step.get('value'),str):
            raise ValueError('fill needs a text value')
        if step['action']=='text' and not isinstance(step.get('expected'),str):
            raise ValueError('text assertion needs expected text')
    return steps

def execute(page,contract):
    result=[]
    for index,step in enumerate(validate(contract)):
        action=step['action']
        try:
            if action=='fill':
                page.get_by_label(step['name'],exact=True).fill(step['value'])
            elif action=='check':
                page.get_by_role('checkbox',name=step['name'],exact=True).check()
            elif action=='click':
                page.get_by_role('button',name=step['name'],exact=True).click()
            else:
                from playwright.sync_api import expect
                expect(page.get_by_role(step.get('role','status'),name=step['name'],exact=True)).to_have_text(step['expected'])
            result.append(dict(kind='passed',step=index,action=action,name=step['name']))
        except Exception as error:
            # Do not leak DOM contents, typed values or potentially sensitive exception text.
            result.append(dict(kind='failed',step=index,action=action,name=step['name'],error_type=type(error).__name__))
            break
    return result

def run(html,contract):
    validate(contract)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch()
        try:
            context=browser.new_context(service_workers='block',accept_downloads=False)
            context.route('**/*',lambda route:route.abort())
            context.route_web_socket('**/*',lambda socket:socket.close())
            page=context.new_page()
            page.set_default_timeout(2000)
            page.on('dialog',lambda dialog:dialog.dismiss())
            context.on('page',lambda popup:popup.close() if popup!=page else None)
            page.set_content(html,wait_until='domcontentloaded')
            return execute(page,contract)
        finally:
            browser.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html'); parser.add_argument('contract')
    args=parser.parse_args()
    try:
        html=Path(args.html).read_text(encoding='utf-8')
        contract=json.loads(Path(args.contract).read_text(encoding='utf-8'))
        result=run(html,contract)
        print(json.dumps(result,indent=2))
        return 1 if any(x['kind']=='failed' for x in result) else 0
    except (ValueError,KeyError,OSError,ImportError) as error:
        print('Cannot run contract: '+type(error).__name__)
        return 2

if __name__=='__main__':
    raise SystemExit(main())

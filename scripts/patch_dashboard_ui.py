#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"

html = INDEX.read_text(encoding="utf-8")

old_toolbar = '''<div class="toolbar">\n<input id="q" placeholder="ค้นหา Ticker / Sector / Flag">\n<select id="valuation"><option value="">Valuation ทั้งหมด</option><option>Cheap</option><option>Fair Value</option><option>Expensive</option><option>Very Expensive</option></select>\n<select id="status"><option value="">Update Status ทั้งหมด</option><option>Current</option><option>New Results Available</option><option>Research Needs Update</option></select>\n<button id="refreshBtn">↻ Reload Dashboard</button>\n</div>'''

new_toolbar = '''<div class="toolbar">\n<button id="refreshBtn">↻ Reload Dashboard</button>\n</div>'''

filter_block = '''\n<div class="toolbar set-filter-toolbar">\n<input id="q" placeholder="ค้นหา Ticker / Sector / Flag">\n<select id="valuation"><option value="">Valuation ทั้งหมด</option><option>Cheap</option><option>Fair Value</option><option>Expensive</option><option>Very Expensive</option></select>\n<select id="status"><option value="">Update Status ทั้งหมด</option><option>Current</option><option>New Results Available</option><option>Research Needs Update</option></select>\n</div>'''

set_footer = '''<div class="set-foot">\n  <span id="setUpdated">ข้อมูลล่าสุด: –</span>\n  <a id="setSource" href="https://www.set.or.th/th/market/index/set/overview" target="_blank" rel="noopener">ที่มา: SET</a>\n</div>'''

css_anchor = '.toolbar-extra{display:flex;justify-content:flex-end;margin:8px 0 14px}'
css_rule = '.set-filter-toolbar{margin:16px 0 0;padding-top:14px;border-top:1px solid var(--line)}'

changed = False

# Move only the 3 filter controls; keep Reload Dashboard in its original toolbar.
if old_toolbar in html:
    html = html.replace(old_toolbar, new_toolbar, 1)
    changed = True

if filter_block not in html:
    if set_footer not in html:
        raise SystemExit('SET footer anchor not found; UI patch aborted safely.')
    html = html.replace(set_footer, set_footer + filter_block, 1)
    changed = True

if css_rule not in html:
    if css_anchor not in html:
        raise SystemExit('CSS anchor not found; UI patch aborted safely.')
    html = html.replace(css_anchor, css_anchor + '\n' + css_rule, 1)
    changed = True

if changed:
    INDEX.write_text(html, encoding="utf-8")
    print('Dashboard UI patched: search / valuation / update status moved below SET Index chart.')
else:
    print('Dashboard UI already patched; no changes needed.')

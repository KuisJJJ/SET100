#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"

html = INDEX.read_text(encoding="utf-8")

old_filter_block = '''<div class="toolbar set-filter-toolbar">
<input id="q" placeholder="ค้นหา Ticker / Sector / Flag">
<select id="valuation"><option value="">Valuation ทั้งหมด</option><option>Cheap</option><option>Fair Value</option><option>Expensive</option><option>Very Expensive</option></select>
<select id="status"><option value="">Update Status ทั้งหมด</option><option>Current</option><option>New Results Available</option><option>Research Needs Update</option></select>
</div>'''

old_industry_block = '''<div class="toolbar-extra"><select id="industryFilter" aria-label="กรองตามอุตสาหกรรม">
<option value="">ทุกอุตสาหกรรม</option>
</select></div>'''

new_filter_block = '''<div class="toolbar" id="setFilterRow">
<input id="q" placeholder="ค้นหา Ticker / Sector / Flag">
<select id="valuation"><option value="">Valuation ทั้งหมด</option><option>Cheap</option><option>Fair Value</option><option>Expensive</option><option>Very Expensive</option></select>
<select id="status"><option value="">Update Status ทั้งหมด</option><option>Current</option><option>New Results Available</option><option>Research Needs Update</option></select>
<select id="industryFilter" aria-label="กรองตามอุตสาหกรรม"><option value="">ทุกอุตสาหกรรม</option></select>
</div>'''

old_css = '''#industryFilter{padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);font:inherit;min-width:190px}
.toolbar-extra{display:flex;justify-content:flex-end;margin:8px 0 14px}
.set-filter-toolbar{margin:16px 0 0;padding-top:14px;border-top:1px solid var(--line)}'''

new_css = '''#setFilterRow{margin:8px 0 14px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
#q{min-width:210px}
#valuation,#status,#industryFilter{min-width:190px}
#industryFilter{padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);font:inherit}'''

changed = False

# Remove the existing 3-control row from inside the SET Index card.
if old_filter_block in html:
    html = html.replace(old_filter_block, "", 1)
    changed = True

# Replace the separate industry row with one unified four-control row.
if old_industry_block in html:
    html = html.replace(old_industry_block, new_filter_block, 1)
    changed = True
elif 'id="setFilterRow"' not in html:
    raise SystemExit('Industry filter anchor not found; UI patch aborted safely.')

# Normalize CSS so all four controls share one responsive row.
if old_css in html:
    html = html.replace(old_css, new_css, 1)
    changed = True
elif '#setFilterRow{' not in html:
    raise SystemExit('Filter CSS anchor not found; UI patch aborted safely.')

if changed:
    INDEX.write_text(html, encoding="utf-8")
    print('Dashboard UI patched: search / valuation / update status / industry aligned on one row below SET Index section.')
else:
    print('Dashboard UI already patched; no changes needed.')

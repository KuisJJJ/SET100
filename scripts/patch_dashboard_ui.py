#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
html = INDEX.read_text(encoding="utf-8")
changed = False

def rep(old, new, count=-1):
    global html, changed
    if old in html:
        html = html.replace(old, new, count)
        changed = True
        return True
    return False

# ------------------------------------------------------------------
# 1) Thai-first UI labels. Values used by filters remain English so
#    the underlying research schema is not changed.
# ------------------------------------------------------------------
replacements = {
    'SET100 DEEP RESEARCH': 'วิจัยหุ้น SET100 เชิงลึก',
    '<span>Market Data</span>': '<span>ราคาหุ้นล่าสุด</span>',
    '<span>Financial Data</span>': '<span>งบการเงิน</span>',
    '<span>Research Review</span>': '<span>ทบทวนบทวิเคราะห์</span>',
    '<div class="update-title">Update Center</div>': '<div class="update-title">ศูนย์อัปเดตข้อมูล</div>',
    'ตรวจข้อมูลล่าสุดจาก data.json, สถานะ Universe, Financials และ Research โดยไม่เขียนทับ Investment Thesis / Score / Team Comment อัตโนมัติ': 'ตรวจราคาหุ้น ดัชนี SET รายชื่อ SET100 งบการเงิน และสถานะบทวิเคราะห์ โดยไม่เขียนทับมุมมองการลงทุนอัตโนมัติ',
    '🔄 Update Data': '🔄 อัปเดตข้อมูล',
    'เปิด GitHub Actions': 'เปิดระบบอัปเดต GitHub',
    '<small>Market Data</small>': '<small>ราคาหุ้น</small>',
    '<small>SET100 Universe</small>': '<small>รายชื่อ SET100</small>',
    '<small>Financials</small>': '<small>งบการเงิน</small>',
    '<small>Research</small>': '<small>บทวิเคราะห์</small>',
    '↻ Reload Dashboard': '↻ โหลด Dashboard ใหม่',
    '<div class="set-title">SET Index</div>': '<div class="set-title">ดัชนี SET</div>',
    '<small>Open</small>': '<small>เปิด</small>',
    '<small>High</small>': '<small>สูงสุด</small>',
    '<small>Low</small>': '<small>ต่ำสุด</small>',
    'ค้นหา Ticker / Sector / Flag': 'ค้นหา Ticker / อุตสาหกรรม / ธีม',
    '<option value="">Valuation ทั้งหมด</option>': '<option value="">มูลค่าหุ้นทั้งหมด</option>',
    '<option>Cheap</option>': '<option value="Cheap">ถูก</option>',
    '<option>Fair Value</option>': '<option value="Fair Value">เหมาะสม</option>',
    '<option>Expensive</option>': '<option value="Expensive">แพง</option>',
    '<option>Very Expensive</option>': '<option value="Very Expensive">แพงมาก</option>',
    '<option value="">Update Status ทั้งหมด</option>': '<option value="">สถานะข้อมูลทั้งหมด</option>',
    '<option>Current</option>': '<option value="Current">ข้อมูลปัจจุบัน</option>',
    '<option>New Results Available</option>': '<option value="New Results Available">มีงบใหม่</option>',
    '<option>Research Needs Update</option>': '<option value="Research Needs Update">ต้องทบทวนบทวิเคราะห์</option>',
    '<summary>ⓘ หลักการอ่าน Dashboard</summary>': '<summary>ⓘ วิธีอ่าน Dashboard</summary>',
    '<p><b>ไม่จัดอันดับหรือเปรียบเทียบหุ้นระหว่างกัน</b> หากมี Peer Comparison จะใช้เฉพาะ Industry / Business Model ที่เกี่ยวข้อง</p>': '<p><b>อันดับในระบบเป็นอันดับตามมูลค่าตลาด ไม่ใช่อันดับความน่าลงทุน</b> การเปรียบเทียบจะใช้เฉพาะบริษัทที่มีอุตสาหกรรมหรือโมเดลธุรกิจใกล้เคียงกัน</p>',
    '<p>Summary แสดง ราคา, Market Cap, P/E, กำไรสุทธิ, Debt / EBITDA และระบุ Moat: มี / ไม่มี พร้อมเหตุผล</p>': '<p>การ์ดหุ้นแสดงราคา มูลค่าตลาด P/E การเติบโตของกำไร หนี้/EBITDA ความได้เปรียบในการแข่งขัน ประเด็นลงทุน ความเสี่ยง และความเห็นของทีม</p>',
}
for old, new in replacements.items():
    rep(old, new)

# Dynamic status labels and N/A display.
rep(
    'function statusLabel(v){if(v==="Current")return"🟢 Current";if(v==="New Results Available")return"🟡 New Results Available";if(v==="Research Needs Update")return"🔴 Research Needs Update";return"⚪ Pending"}',
    'function statusLabel(v){if(v==="Current")return"🟢 ข้อมูลปัจจุบัน";if(v==="New Results Available")return"🟡 มีงบใหม่";if(v==="Research Needs Update")return"🔴 ต้องทบทวนบทวิเคราะห์";return"⚪ รอดำเนินการ"}'
)
rep('):"N/A"}', '):"ไม่มีข้อมูล"}')

# Update-center language.
rep('`🟢 Validated (${uv.officialCount||100})`', '`🟢 ตรวจแล้ว (${uv.officialCount||100})`')
rep('`🔴 Review required`', '`🔴 ต้องตรวจสอบ`')
rep('"⚪ Not checked"', '"⚪ ยังไม่ได้ตรวจ"')
rep('"🟢 No new flag"', '"🟢 ยังไม่มีงบใหม่"')
rep('`🔴 ${ru} บริษัทต้อง Review`', '`🔴 ${ru} บริษัทต้องทบทวน`')
rep('"🟢 Current"', '"🟢 ปัจจุบัน"')
rep('<b>⚠️ Universe Alert</b>', '<b>⚠️ แจ้งเตือนรายชื่อ SET100</b>')
rep('Official SET100:', 'SET100 ทางการ:')
rep('Master:', 'ในฐานข้อมูล:')
rep('Missing:', 'ขาด:')
rep('Extra:', 'เกิน:')
rep('Duplicate:', 'ซ้ำ:')
rep('"None"', '"ไม่มี"')

# ------------------------------------------------------------------
# 2) Card labels in Thai.
# ------------------------------------------------------------------
card_replacements = {
    'MCap Rank #${x.rank}': 'อันดับมูลค่าตลาด #${x.rank}',
    '<div class="meta">Overall Score</div>': '<div class="meta">คะแนนรวม</div>',
    '<small>Market Cap</small>': '<small>มูลค่าตลาด</small>',
    '<small>Debt / EBITDA</small>': '<small>หนี้ / EBITDA</small>',
    '↻ Update ${x.ticker}': '↻ อัปเดต ${x.ticker}',
    '<div class="section"><h3>Moat</h3>': '<div class="section"><h3>ความได้เปรียบในการแข่งขัน (Moat)</h3>',
    '<div class="section"><h3>Debt / EBITDA</h3>': '<div class="section"><h3>หนี้ / EBITDA</h3>',
    '<div class="section"><h3>Industry Comparison</h3>': '<div class="section"><h3>เปรียบเทียบกับบริษัทในอุตสาหกรรม</h3>',
    '<div class="section"><h3>Investment Thesis</h3>': '<div class="section"><h3>ประเด็นลงทุน</h3>',
    '<div class="section"><h3>Bear Thesis</h3>': '<div class="section"><h3>ประเด็นลบ / กรณีลงทุนผิด</h3>',
    '<details><summary>เปิด Stock Deep Research Framework 11 หัวข้อ</summary>': '<details><summary>เปิดบทวิเคราะห์เชิงลึก 11 หัวข้อ</summary>',
    '<div class="section"><h3>ตลาดกำลังเชื่ออะไร (What Market Believes)</h3>': '<div class="section"><h3>สิ่งที่ตลาดกำลังเชื่อ</h3>',
    '<div class="section"><h3>ตลาดอาจมองข้ามอะไร (What Market Might Be Missing)</h3>': '<div class="section"><h3>สิ่งที่ตลาดอาจมองข้าม</h3>',
    '<div class="section"><h3>Data Freshness</h3><div>Market Data: ${x.marketDataUpdated||"–"}</div><div>Financial Data: ${x.financialDataUpdated||"–"}</div><div>Research Reviewed: ${x.researchReviewed||"–"}</div></div>': '<div class="section"><h3>ความสดของข้อมูล</h3><div>ราคาหุ้น: ${x.marketDataUpdated||"–"}</div><div>งบการเงิน: ${x.financialDataUpdated||"–"}</div><div>ทบทวนบทวิเคราะห์: ${x.researchReviewed||"–"}</div></div>',
}
for old, new in card_replacements.items():
    rep(old, new)

# Translate framework headings at display time without changing the research schema.
framework_old = '${(Object.entries(x.framework||{})).map(([k,v])=>`<div class="section"><h3>${k}</h3><div>${v}</div></div>`).join("")}'
framework_new = '${(Object.entries(x.framework||{})).map(([k,v])=>`<div class="section"><h3>${frameworkTitle(k)}</h3><div>${v}</div></div>`).join("")}'
rep(framework_old, framework_new)

anchor = 'function industryMatch(x){\n const sel=document.getElementById("industryFilter");\n return !sel || !sel.value || x.sector===sel.value;\n}\n'
helpers = r'''function industryMatch(x){
 const sel=document.getElementById("industryFilter");
 return !sel || !sel.value || x.sector===sel.value;
}
function frameworkTitle(k){
 const m={
  "1. Management":"1. ผู้ถือหุ้นและผู้บริหาร",
  "2. Product / Moat":"2. ธุรกิจและความได้เปรียบการแข่งขัน",
  "3. TAM / Growth Runway":"3. ขนาดตลาดและพื้นที่การเติบโต",
  "4. Positive Catalysts":"4. ปัจจัยบวกต่อราคาหุ้น",
  "5. Competitors":"5. คู่แข่ง",
  "6. Revenue Growth & Margin":"6. การเติบโตของรายได้และอัตรากำไร",
  "7. Regulation":"7. กฎระเบียบที่เกี่ยวข้อง",
  "8. Narrative & Sentiment":"8. เรื่องเล่าตลาดและความเชื่อมั่น",
  "9. Valuation Effect":"9. ผลของมูลค่าหุ้น",
  "10. Earnings & Macro":"10. ผลประกอบการและเศรษฐกิจมหภาค",
  "11. Risk Radar":"11. เรดาร์ความเสี่ยง"
 };
 return m[k]||k;
}
function escText(s){return String(s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
function commentKey(t){return `set100-team-comment-${t}`;}
function getTeamComment(t,master){const v=localStorage.getItem(commentKey(t));return v===null?(master||""):v;}
function saveTeamComment(t){
 const el=document.getElementById(`team-comment-${t}`); if(!el)return;
 localStorage.setItem(commentKey(t),el.value);
 const m=document.getElementById(`team-comment-msg-${t}`);if(m){m.textContent="บันทึกในอุปกรณ์นี้แล้ว";setTimeout(()=>m.textContent="",1800)}
}
function resetTeamComment(t,master){
 localStorage.removeItem(commentKey(t));
 const el=document.getElementById(`team-comment-${t}`);if(el)el.value=master||"";
 const m=document.getElementById(`team-comment-msg-${t}`);if(m){m.textContent="คืนค่าจาก Master แล้ว";setTimeout(()=>m.textContent="",1800)}
}
'''
if anchor in html:
    html = html.replace(anchor, helpers, 1)
    changed = True
elif 'function frameworkTitle(k)' not in html:
    raise SystemExit('JS helper anchor not found; patch aborted safely.')

# Editable team-comment area. This intentionally uses localStorage because a
# public GitHub Pages site cannot securely write to the repository without a
# server-side authenticated endpoint.
old_comment = r'''<div class="team-comment-wrap">
 <h3>ความเห็นของทีม</h3>
 <div class="team-comment-box">${x.teamComment ? x.teamComment : '<span class="team-comment-empty">ยังไม่มีความเห็นของทีม</span>'}</div>
 <div class="team-comment-meta">แก้ไขจาก Master Excel → 06_Deep_Research → Team Comment</div>
 </div>'''
new_comment = r'''<div class="team-comment-wrap">
 <h3>ความเห็นของทีม</h3>
 <textarea class="team-comment-box team-comment-input" id="team-comment-${x.ticker}" placeholder="พิมพ์ความเห็นของทีมที่นี่...">${escText(getTeamComment(x.ticker,x.teamComment))}</textarea>
 <div class="team-comment-actions"><button type="button" onclick="saveTeamComment('${x.ticker}')">💾 บันทึกความเห็น</button><button type="button" class="btn-soft" onclick="resetTeamComment('${x.ticker}',${JSON.stringify(x.teamComment||'')})">คืนค่าจาก Master</button><span id="team-comment-msg-${x.ticker}" class="team-comment-saved"></span></div>
 <div class="team-comment-meta">บันทึกจากหน้าเว็บไว้ในอุปกรณ์/เบราว์เซอร์นี้ • ค่าเริ่มต้นอ่านจาก Master Excel • ยังไม่ sync กลับ GitHub อัตโนมัติ</div>
 </div>'''
rep(old_comment, new_comment)

# ------------------------------------------------------------------
# 3) More lively but professional visual theme.
# ------------------------------------------------------------------
fun_css = r'''
/* v10 playful-professional theme */
:root{--bg:#f8f7ff;--card:#ffffff;--ink:#18233b;--muted:#68738a;--line:#e4e2f1;--navy:#32245f;--blue:#5a54e8;--green:#178f66;--red:#d6455d;--amber:#d9822b;--pink:#f05ea8;--cyan:#29a9c7;--violet:#7c5ce7;--yellow:#ffd76a}
body{background:radial-gradient(circle at 8% 4%,#fff1f7 0,transparent 23%),radial-gradient(circle at 94% 10%,#eefcff 0,transparent 26%),linear-gradient(180deg,#f8f7ff 0%,#f5f9ff 100%)}
header{background:linear-gradient(120deg,#30205f 0%,#5547c8 47%,#218fac 100%);position:relative;overflow:hidden}
header:after{content:"";position:absolute;width:260px;height:260px;border-radius:50%;background:rgba(255,215,106,.16);right:-70px;top:-100px}
.kpi{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.18);backdrop-filter:blur(5px)}
.card{border-color:#e7e2f4;box-shadow:0 10px 30px rgba(65,54,125,.08)}
.update-card{background:linear-gradient(135deg,#ffffff 0%,#fbf7ff 55%,#f0fbff 100%);border-top:4px solid var(--violet)}
.set-card{background:linear-gradient(180deg,#fff 0%,#fbfcff 100%);border-top:4px solid var(--cyan)}
.btn-primary{background:linear-gradient(135deg,var(--violet),#4e74e8)}
button{background:linear-gradient(135deg,#33245f,#4d3f91);transition:transform .15s ease,box-shadow .15s ease}
button:hover{transform:translateY(-1px);box-shadow:0 6px 14px rgba(50,36,95,.18)}
.btn-soft{background:#f1efff;color:#5745c6;border:1px solid #dcd5ff}
.score{color:#654ee8}.tag{background:linear-gradient(135deg,#f1efff,#ecfbff);color:#463989}
.metric:nth-child(1){background:#fff4f9}.metric:nth-child(2){background:#f3f1ff}.metric:nth-child(3){background:#effaff}.metric:nth-child(4){background:#f0fbf6}.metric:nth-child(5){background:#fff8e8}
.cheap{background:#e7f8ef;color:#147b56}.fair{background:#eeeaff;color:#5947c8}.exp{background:#fff2df;color:#a65b00}.vexp{background:#ffe7ec;color:#bd2f4b}
#setFilterRow{background:#fff;padding:12px;border:1px solid #e7e2f4;border-radius:14px;box-shadow:0 7px 20px rgba(65,54,125,.06)}
input,select{border-color:#ddd8ee;box-shadow:inset 0 1px 0 rgba(255,255,255,.7)}
input:focus,select:focus,.team-comment-input:focus{outline:3px solid rgba(124,92,231,.14);border-color:#8b74e8}
.team-comment-input{width:100%;resize:vertical;font-family:inherit;background:linear-gradient(180deg,#fffdf2,#fff);border:1px solid #eadf9c}
.team-comment-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:7px}.team-comment-actions button{padding:7px 10px;font-size:11px}.team-comment-saved{font-size:11px;color:var(--green);font-weight:700}
.chart-line{stroke:#6654e8}.chart-dot{fill:#f05ea8}.set-stat:nth-child(1){background:#f3f1ff}.set-stat:nth-child(2){background:#f0fbf6}.set-stat:nth-child(3){background:#fff1f5}.set-stat:nth-child(4){background:#effaff}
'''
if '/* v10 playful-professional theme */' not in html:
    html = html.replace('</style>', fun_css + '\n</style>', 1)
    changed = True

# Translate update-log phrases.
for old,new in {
    '1/4 กำลังตรวจ data.json เวอร์ชันล่าสุด...':'1/4 กำลังตรวจข้อมูลเวอร์ชันล่าสุด...',
    '2/4 โหลด Market Data / Rank ล่าสุดแล้ว':'2/4 โหลดราคาหุ้นและอันดับล่าสุดแล้ว',
    '3/4 ตรวจ Universe / Financial / Research Status...':'3/4 ตรวจรายชื่อ SET100 / งบการเงิน / สถานะบทวิเคราะห์...',
    'Error: ':'ข้อผิดพลาด: '
}.items(): rep(old,new)

if changed:
    INDEX.write_text(html, encoding='utf-8')
    print('Dashboard patched: Thai-first labels, editable local team comments, playful-professional theme.')
else:
    print('Dashboard patch already applied; no changes needed.')

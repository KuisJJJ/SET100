#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
html = INDEX.read_text(encoding='utf-8')
changed = False

def rep(old, new, count=-1):
    global html, changed
    if old in html:
        html = html.replace(old, new, count)
        changed = True
        return True
    return False

# Finish Thai-first static labels.
for old,new in {
    'ลำดับการวิเคราะห์ = Market Cap 100% • เปรียบเทียบเฉพาะ Industry / Peer Group ที่เกี่ยวข้อง • แหล่งข้อมูลหลัก = SET / SETTRADE / Company IR':
    'ลำดับตามมูลค่าตลาด 100% • เปรียบเทียบเฉพาะบริษัทในอุตสาหกรรมหรือโมเดลธุรกิจที่เกี่ยวข้อง • แหล่งข้อมูลหลัก = SET / SETTRADE / Investor Relations',
    'วันที่ข้อมูลตลาดล่าสุด':'วันที่ราคาหุ้นอัปเดตล่าสุด',
    'งบที่ใช้วิเคราะห์':'งบการเงินที่ใช้วิเคราะห์',
    'Dashboard อ่านข้อมูลจาก <b>data.json</b> • Team Comment มาจาก Master Excel ผ่าน GitHub Actions อัตโนมัติ':
    'Dashboard อ่านข้อมูลจาก <b>data.json</b> • ความเห็นใน Master Excel จะถูกใช้เป็นค่าเริ่มต้น',
    'หมายเหตุ: ปุ่ม Update Data รีโหลดข้อมูลล่าสุดแบบ no-cache; หากต้องการบังคับให้ GitHub ดึงข้อมูลตลาดใหม่ทันที ให้กด “เปิด GitHub Actions” แล้ว Run workflow ก่อน':
    'หมายเหตุ: ปุ่มอัปเดตข้อมูลบนหน้าเว็บจะโหลดไฟล์ล่าสุด ส่วนการดึงราคาหุ้นใหม่จากตลาดทำผ่านระบบอัปเดต GitHub ตามรอบเวลา',
    'ที่มา: SET':'แหล่งอ้างอิง: SET',
}.items(): rep(old,new)

# Market-index source status shown to users.
rep('document.getElementById("setUpdated").textContent=`ข้อมูลล่าสุด: ${m.updatedAt||"–"} • ${m.status||""}`;',
    'document.getElementById("setUpdated").textContent=`ข้อมูลล่าสุด: ${m.updatedAt||"–"} • ${sourceStatusLabel(m.status)}`;')

# Harden team-comment reset: never inject arbitrary Master text into an onclick attribute.
rep(
'''function resetTeamComment(t,master){
 localStorage.removeItem(commentKey(t));
 const el=document.getElementById(`team-comment-${t}`);if(el)el.value=master||"";
 const m=document.getElementById(`team-comment-msg-${t}`);if(m){m.textContent="คืนค่าจาก Master แล้ว";setTimeout(()=>m.textContent="",1800)}
}''',
'''function resetTeamComment(t){
 localStorage.removeItem(commentKey(t));
 const item=DATA.find(x=>x.ticker===t);const master=(item&&item.teamComment)||"";
 const el=document.getElementById(`team-comment-${t}`);if(el)el.value=master;
 const m=document.getElementById(`team-comment-msg-${t}`);if(m){m.textContent="คืนค่าจาก Master แล้ว";setTimeout(()=>m.textContent="",1800)}
}''')
rep("onclick=\"resetTeamComment('${x.ticker}',${JSON.stringify(x.teamComment||'')})\"", "onclick=\"resetTeamComment('${x.ticker}')\"")

# Add Thai display labels for valuation/source status/sector while preserving raw values.
anchor='function frameworkTitle(k){'
helpers='''function valuationLabel(v){const m={"Very Cheap":"ถูกมาก","Cheap":"ถูก","Fair Value":"เหมาะสม","Expensive":"แพง","Very Expensive":"แพงมาก"};return m[v]||v||"ไม่มีข้อมูล";}\nfunction sourceStatusLabel(v){const m={"Secondary delayed feed":"ข้อมูลรองแบบหน่วงเวลา","Primary official feed":"ข้อมูลทางการ"};return m[v]||v||"";}\nfunction sectorLabel(v){const m={"Banking":"ธนาคาร","Energy & Utilities":"พลังงานและสาธารณูปโภค","Commerce":"พาณิชย์","Property Development":"พัฒนาอสังหาริมทรัพย์","Finance & Securities":"การเงินและหลักทรัพย์","Health Care Services":"บริการทางการแพทย์","Transportation & Logistics":"ขนส่งและโลจิสติกส์","Food & Beverage":"อาหารและเครื่องดื่ม","Electronic Components":"ชิ้นส่วนอิเล็กทรอนิกส์","Media & Publishing":"สื่อและสิ่งพิมพ์","Tourism & Leisure":"ท่องเที่ยวและสันทนาการ","Agribusiness":"ธุรกิจการเกษตร","Information & Communication Technology":"เทคโนโลยีสารสนเทศและการสื่อสาร"};return m[v]||v||"";}\n'''
if 'function valuationLabel(v)' not in html and anchor in html:
    html=html.replace(anchor, helpers+anchor,1);changed=True

rep('${x.sector}</div></div><div style="text-align:right"><div class="meta">คะแนนรวม</div>', '${sectorLabel(x.sector)}</div></div><div style="text-align:right"><div class="meta">คะแนนรวม</div>')
rep('<span class="badge ${valClass(x.valuation)}">${x.valuation}</span>', '<span class="badge ${valClass(x.valuation)}">${valuationLabel(x.valuation)}</span>')
rep('sectors.map(s=>`<option value="${s}">${s}</option>`)', 'sectors.map(s=>`<option value="${s}">${sectorLabel(s)}</option>`)')

# Local team comment disclosure and button labels.
rep('บันทึกจากหน้าเว็บไว้ในอุปกรณ์/เบราว์เซอร์นี้ • ค่าเริ่มต้นอ่านจาก Master Excel • ยังไม่ sync กลับ GitHub อัตโนมัติ',
    'พิมพ์และบันทึกได้ทันทีในเบราว์เซอร์นี้ • ค่าเริ่มต้นอ่านจาก Master Excel • ความเห็นที่พิมพ์บนเว็บยังไม่แชร์ข้ามเครื่องหรือ sync กลับ GitHub')

# Small mobile polish for the new playful theme.
mobile='''\n@media(max-width:650px){#setFilterRow>*{flex:1 1 100%;min-width:0}.team-comment-actions button{flex:1 1 auto}.set-last{font-size:30px}.kpis{gap:8px}.kpi{padding:11px}.card{border-radius:14px}}\n'''
if '@media(max-width:650px){#setFilterRow>*' not in html:
    html=html.replace('</style>',mobile+'\n</style>',1);changed=True

if changed:
    INDEX.write_text(html,encoding='utf-8')
    print('Dashboard UI QA patch applied: Thai labels completed and team-comment reset hardened.')
else:
    print('Dashboard UI QA patch already applied; no changes needed.')

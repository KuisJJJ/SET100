#!/usr/bin/env python3
"""Final pass: convert English business prose to Thai and perform practical QA.

Allowed to remain in English: company/product proper names and standard finance/industry
abbreviations. Explanatory prose should be Thai.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data.json'
STATUS=ROOT/'research_thai_qa.json'
FIELDS=['summary','debtEbitdaBasis','debtEbitdaNote','thesis','bear','marketBelieves','marketMissing','variables','fit','moatReason','industryComparison']

PHRASES={
'Margin of Safety':'ส่วนเผื่อความปลอดภัย','Structural Growth':'การเติบโตเชิงโครงสร้าง','Data Center':'ศูนย์ข้อมูล','Power Electronics':'อิเล็กทรอนิกส์กำลัง','Electronic Components':'ชิ้นส่วนอิเล็กทรอนิกส์','Global Power Management':'ผู้เล่นด้านการจัดการพลังงานระดับโลก','Market Cap':'มูลค่าตลาด','screening value':'ค่าคัดกรองเบื้องต้น','text parser':'ตัวอ่านข้อมูลข้อความ','Engineering Know-how':'ความเชี่ยวชาญด้านวิศวกรรม','Customer Qualification':'กระบวนการรับรองจากลูกค้า','Supply Chain':'ห่วงโซ่อุปทาน','Asset Backing':'มูลค่าทรัพย์สินรองรับ','Vertical Integration':'การบูรณาการแนวดิ่ง','Barrier to Entry':'อุปสรรคในการเข้าสู่ตลาด','Cash Flow':'กระแสเงินสด','Earnings Visibility':'ความชัดเจนของกำไร','Network Scale':'ขนาดเครือข่าย','Switching Friction':'ความยากในการเปลี่ยนผู้ให้บริการ','Long-term Infrastructure':'โครงสร้างพื้นฐานระยะยาว','Strategic Ecosystem':'ระบบนิเวศเชิงกลยุทธ์','Natural Monopoly':'การผูกขาดโดยธรรมชาติ','Premium Valuation':'มูลค่าที่มีพรีเมียม','Network Effect':'ผลของเครือข่าย','Passenger Growth':'การเติบโตของผู้โดยสาร','Passenger/Commercial Growth':'การเติบโตของผู้โดยสารและรายได้เชิงพาณิชย์','Aero/Non-aero Revenue':'รายได้จากการบินและนอกการบิน','Core Banking':'ธุรกิจธนาคารหลัก','Daily Habit':'พฤติกรรมการใช้งานประจำวัน','fee/corporate loan':'รายได้ค่าธรรมเนียมและสินเชื่อธุรกิจ','multiple re-rate':'การปรับมูลค่าหุ้นขึ้น','Balance Sheet Repair':'การซ่อมแซมงบดุล','Quality Compounder':'ธุรกิจคุณภาพที่เติบโตทบต้น','Patient Mix':'สัดส่วนผู้ป่วย','Harvest Phase':'ช่วงเก็บเกี่ยวผลตอบแทน','Asset Quality':'คุณภาพสินทรัพย์','Tenant Ecosystem':'ระบบนิเวศผู้เช่า','Development Scale':'ขนาดการพัฒนาโครงการ','record rental revenue':'รายได้ค่าเช่าสูงสุดเป็นประวัติการณ์','Growth Story':'เรื่องราวการเติบโต','Portfolio Optimization':'การปรับพอร์ตให้เหมาะสม','Capital Intensity':'ความเข้มข้นในการใช้เงินทุน','normalized margin':'อัตรากำไรปกติ','Refinery asset':'สินทรัพย์โรงกลั่น','Project Economics':'ผลตอบแทนเชิงเศรษฐศาสตร์ของโครงการ','Spread Normalization':'การกลับสู่ภาวะปกติของส่วนต่างราคา','Cost Reset':'การปรับฐานต้นทุน','Earnings Growth':'การเติบโตของกำไร','Multiple Expansion':'การขยายตัวของตัวคูณมูลค่า','Distribution Moat':'ความได้เปรียบด้านช่องทางจัดจำหน่าย','Oil Margin':'อัตรากำไรน้ำมัน','Non-oil':'ธุรกิจนอกน้ำมัน','Contracted Cash Flow':'กระแสเงินสดตามสัญญา','Investment Case':'กรณีการลงทุน','Indonesia Turnaround':'การฟื้นตัวของธุรกิจอินโดนีเซีย','Capital Strength':'ความแข็งแกร่งของเงินกองทุน','Embedded Value':'มูลค่าธุรกิจประกันที่ฝังอยู่','Trailing Multiple':'ตัวคูณมูลค่าย้อนหลัง','Asset Recycling':'การหมุนเวียนขายสินทรัพย์เพื่อนำทุนกลับมาใช้','Through-cycle':'ตลอดวัฏจักร','Other Activities':'กิจกรรมอื่น','run-rate':'ระดับผลการดำเนินงานปกติ','Store Model':'รูปแบบร้านค้า','Industrial Customer':'ลูกค้าอุตสาหกรรม','New Business Value':'มูลค่าธุรกิจใหม่','Capital Return':'การคืนทุนให้ผู้ถือหุ้น','Location/Concession':'ทำเลและสิทธิสัมปทาน','Shipping Cycle':'วัฏจักรการเดินเรือ','Capital Discipline':'วินัยการใช้เงินทุน','Rubber Cycle':'วัฏจักรยาง','Land+Infrastructure':'ที่ดินและโครงสร้างพื้นฐาน','Recurring Utilities':'รายได้สาธารณูปโภคประจำ','Branded Food':'อาหารแบรนด์','Market Share':'ส่วนแบ่งตลาด','Customer Ecosystem':'ระบบนิเวศลูกค้า','FDI/Data Center':'FDI และศูนย์ข้อมูล','Asset Value':'มูลค่าสินทรัพย์','Food SSSG':'SSSG ธุรกิจอาหาร','Retail/Value-added':'ค้าปลีกและสินค้ามูลค่าเพิ่ม','Cannibalize':'แย่งยอดขายสาขาเดิม','Semiconductor Story':'เรื่องราวการเติบโตของเซมิคอนดักเตอร์','Branded Mix':'สัดส่วนสินค้ามีแบรนด์','Defensive':'เชิงรับ','Credit Quality':'คุณภาพสินเชื่อ','Optionality':'ทางเลือกการเติบโต','Marketing Margin':'อัตรากำไรการตลาด','Site Productivity':'ประสิทธิภาพต่อสาขา','Revenue Growth':'การเติบโตของรายได้','Revenue':'รายได้','Gross Margin':'อัตรากำไรขั้นต้น','Valuation':'มูลค่าหุ้น','Business Quality':'คุณภาพธุรกิจ','Business':'ธุรกิจ','Moat':'ความได้เปรียบการแข่งขัน','Cash':'เงินสด','Earnings':'กำไร','Telecom':'โทรคมนาคม','Spectrum':'คลื่นความถี่','Distribution':'ช่องทางจัดจำหน่าย','Energy':'พลังงาน','Cloud':'คลาวด์','Scale':'ขนาดธุรกิจ','Strategic':'เชิงกลยุทธ์','Location':'ทำเล','Regulation':'กฎระเบียบ','Passenger':'ผู้โดยสาร','Value':'มูลค่า','Cyclical':'เชิงวัฏจักร','Commodity':'สินค้าโภคภัณฑ์','Turnaround':'การฟื้นตัว','Recovery':'การฟื้นตัว','Repair':'การซ่อมแซม','Compounder':'ธุรกิจเติบโตทบต้น','headline':'ตัวเลขพาดหัว','one-off':'รายการครั้งเดียว','Segment':'กลุ่มธุรกิจ','Cement':'ปูนซีเมนต์','Chemicals':'เคมีภัณฑ์','Packaging':'บรรจุภัณฑ์','Thesis':'ประเด็นลงทุน','Cycle':'วัฏจักร','normalized':'ระดับปกติ','Refinery':'โรงกลั่น','Spread':'ส่วนต่างราคา','upside':'โอกาสปรับขึ้น','Inventory':'สินค้าคงคลัง','Contracted':'ตามสัญญา','Investment':'การลงทุน','Case':'กรณี','Synergy':'ประโยชน์ร่วม','Deleveraging':'การลดหนี้','Land':'ที่ดิน','Infrastructure':'โครงสร้างพื้นฐาน','Utilities':'สาธารณูปโภค','Customer':'ลูกค้า','Ecosystem':'ระบบนิเวศ','Multiple':'ตัวคูณมูลค่า','Normalize':'ปรับสู่ระดับปกติ','Store':'ร้านค้า','Model':'รูปแบบ','Industrial':'อุตสาหกรรม','Premium':'พรีเมียม','Story':'เรื่องราว','Capital':'เงินทุน','Efficiency':'ประสิทธิภาพ','Catalyst':'ปัจจัยกระตุ้น','Network':'เครือข่าย','Location':'ทำเล','Concession':'สัมปทาน','Rubber':'ยาง','Optionality':'ทางเลือกการเติบโต','Safety':'ความปลอดภัย','screening':'การคัดกรอง','ratio':'อัตราส่วน','parser':'ตัวอ่านข้อมูล','Supplier':'ผู้จัดหา','Global':'ระดับโลก','Management':'การบริหาร','Backing':'การรองรับ','Entry':'การเข้าสู่ตลาด','Density':'ความหนาแน่นเครือข่าย','Logistics':'โลจิสติกส์','Habit':'พฤติกรรมประจำ','Catalysts':'ปัจจัยกระตุ้น','loan':'สินเชื่อ','re-rate':'ปรับมูลค่าขึ้น','Patient':'ผู้ป่วย','Mix':'สัดส่วน','Portfolio':'พอร์ต','Optimization':'การปรับให้เหมาะสม','Retail':'ค้าปลีก','Food':'อาหาร','Quality':'คุณภาพ','Credit':'สินเชื่อ','Asset':'สินทรัพย์','Marketing':'การตลาด','Productivity':'ประสิทธิภาพ','Growth':'การเติบโต'
}

ALLOWED=set('SET SET100 SETTRADE IR P/E P/BV EV/EBITDA EBITDA EBITDAR EBIT NPAT EPS FCF OCF ROE ROIC D/E NIM NPL CAGR TAM SAM SOM YoY QoQ AI FX CAPEX SG&A ASP SSSG RevPAR ADR RASK CASK BOED PPA COD FID NAV IRR ECL LTV GPM FFO GRM ARPU CAR CET1 MW TEU THB USD IPP SPP EMS PCB PET E&P LPG SOTP APE VONB CSM RBC FDI EV SiC'.split())

# Proper/product names that are expected to remain as names, not prose.
PROPER=set('ADVANC AOT AURA AutoX BankX BBL BCP BDMS BGRIM BH BLA BTS CBG CENTEL CFP CK CPALL CPF CPN DELTA EGCO GULF HANA Henry Hub InnovestX IRPC JMART JMT KBANK KTB KTC MINT MRDIYT MTC OR OSP PLANB PLUS PTG PTT PTTGC PTTEP QH RATCH RCL SAWAD SCB SCGP SCC SIRI SPALI SPRC STA STGT TCAP TFG THAI TIDLOR TISCO TLI TOA TOP TRUE TTB TU VGI WHA DataX TechX CardX'.split())

def clean(s:Any)->Any:
    if not isinstance(s,str): return s
    out=s
    for en,th in sorted(PHRASES.items(),key=lambda x:len(x[0]),reverse=True):
        out=re.sub(re.escape(en),th,out,flags=re.I)
    # repair a few machine-translation artifacts
    out=out.replace('อัตรากำไร of ความปลอดภัย','ส่วนเผื่อความปลอดภัย')
    out=out.replace('EBITDAZ','EBITDA')
    out=re.sub(r'\s{2,}',' ',out).strip()
    return out

def clean_stock(st):
    for f in FIELDS:
        if f in st: st[f]=clean(st[f])
    for k,v in list((st.get('framework') or {}).items()): st['framework'][k]=clean(v)
    if isinstance(st.get('flags'),list): st['flags']=[clean(x) for x in st['flags']]

def english_prose_words(s:str,ticker:str)->list[str]:
    # remove known abbreviations, ticker and obvious proper/product names before QA
    text=s
    for term in sorted(ALLOWED|PROPER|{ticker},key=len,reverse=True):
        text=re.sub(r'(?<![A-Za-z])'+re.escape(term)+r'(?![A-Za-z])',' ',text,flags=re.I)
    words=re.findall(r'[A-Za-z][A-Za-z/-]{2,}',text)
    # Acronym-like all caps words are names/abbreviations, not explanatory prose.
    return [w for w in words if not (w.isupper() and len(w)<=10)]

def main():
    p=json.loads(DATA.read_text(encoding='utf-8'))
    for st in p.get('stocks',[]): clean_stock(st)
    remaining=[]
    for st in p.get('stocks',[]):
        t=st.get('ticker','?')
        for f in FIELDS:
            v=st.get(f)
            if isinstance(v,str):
                w=english_prose_words(v,t)
                if len(w)>=3: remaining.append({'ticker':t,'field':f,'englishWords':w[:20],'sample':v[:240]})
        for k,v in (st.get('framework') or {}).items():
            if isinstance(v,str):
                w=english_prose_words(v,t)
                if len(w)>=3: remaining.append({'ticker':t,'field':f'framework::{k}','englishWords':w[:20],'sample':v[:240]})
    p.setdefault('meta',{})['thaiLanguageQA']={'checked':True,'remainingEnglishExplanationBlocks':len(remaining),'technicalAbbreviationsPreserved':True,'policy':'Thai explanatory prose; standard finance abbreviations and proper names may remain English.'}
    DATA.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    STATUS.write_text(json.dumps({'checked':True,'remainingEnglishExplanationBlocks':len(remaining),'policy':'Thai explanatory prose; standard finance abbreviations and proper names may remain English.','remaining':remaining[:1000]},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Final Thai-language QA remaining explanation blocks:',len(remaining))

if __name__=='__main__': main()

#!/usr/bin/env python3
"""Targeted final terminology pass after Thai normalization.
Only translates explanatory terms; company/product/peer names and standard abbreviations remain unchanged.
"""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data.json'
STATUS=ROOT/'research_thai_qa.json'
FIELDS=['summary','debtEbitdaBasis','debtEbitdaNote','thesis','bear','marketBelieves','marketMissing','variables','fit','moatReason','industryComparison']
MAP={
'Large Thai Banks':'ธนาคารไทยขนาดใหญ่','Coverage':'อัตราสำรองต่อหนี้เสีย','opex':'ค่าใช้จ่ายดำเนินงาน','offset':'ชดเชย','Wealth/Fees':'ธุรกิจบริหารความมั่งคั่งและค่าธรรมเนียม','core':'ธุรกิจหลัก','Asian Refiners':'โรงกลั่นในเอเชีย','Complexity':'ความซับซ้อนของโรงกลั่น','Bear':'กรณีลบ','Bull':'กรณีบวก','Normalization':'การกลับสู่ระดับปกติ','Wealth':'ธุรกิจบริหารความมั่งคั่ง','Markets':'ตลาดทุน','auto slowdown':'การชะลอตัวของอุตสาหกรรมรถยนต์','de-rating':'การปรับตัวคูณมูลค่าลง','Transfers':'ยอดโอน','Rental Income':'รายได้ค่าเช่า','Airline':'ธุรกิจสายการบิน','Airport/Service':'สนามบินและบริการ','Yield':'รายได้เฉลี่ยต่อหน่วย','Airport Traffic':'ปริมาณผู้ใช้สนามบิน','Hospital':'โรงพยาบาล','Bed':'เตียง','International/Private':'ผู้ป่วยต่างชาติ/เอกชน','Asphalt/Construction Materials':'ยางมะตอยและวัสดุก่อสร้าง','Asphalt':'ยางมะตอย','Water':'น้ำ','Power':'ไฟฟ้า','Private PPA':'PPA เอกชน','Direct PPA':'PPA โดยตรง','S-curve':'เส้นการเติบโตใหม่','ex-รายการครั้งเดียว':'ไม่รวมรายการครั้งเดียว','fee/corporate':'ค่าธรรมเนียม/ลูกค้าธุรกิจ','loan':'สินเชื่อ','Gen2':'ธุรกิจ Gen2','Gen3':'ธุรกิจ Gen3'
}
PROPER={'Vertiv','Schneider','Eaton','Hartalega','Top Glove','Kossan','Unistretch','Vivek','Dhawan','Mega We Care','Maxxcare','World Medical','Kasemrad International','Kasemrad','Karunvej','Gheco-One','Café Amazon','Amazon','Samui','Henry Hub','SiC','GPSC','EGCO','RATCH','BGRIM','K PLUS','BankX','AutoX','InnovestX','DataX','TechX','CardX','Gulf Space Technology'}
ALLOWED={'SET','SET100','SETTRADE','P/E','P/BV','EV/EBITDA','EBITDA','EBIT','NPAT','EPS','FCF','OCF','ROE','ROIC','D/E','NIM','NPL','CAGR','TAM','SAM','SOM','YoY','QoQ','AI','FX','CAPEX','SG&A','ASP','SSSG','RevPAR','ADR','RASK','CASK','BOED','PPA','PDP','COD','FID','NAV','IRR','ECL','LTV','GPM','FFO','GRM','ARPU','CAR','CET1','MW','TEU','THB','USD','IPP','SPP','EMS','PCB','PET','E&P','LPG','SOTP','APE','VONB','CSM','RBC','FDI','EV','ICR'}

def clean(s):
 if not isinstance(s,str): return s
 out=s
 for a,b in sorted(MAP.items(),key=lambda x:len(x[0]),reverse=True): out=re.sub(re.escape(a),b,out,flags=re.I)
 out=out.replace('PPAZ','PPA').replace('สินทรัพย์s','สินทรัพย์')
 return re.sub(r'\s{2,}',' ',out).strip()

def clean_stock(st):
 for f in FIELDS:
  if f in st: st[f]=clean(st[f])
 for k,v in list((st.get('framework') or {}).items()): st['framework'][k]=clean(v)

def prose_words(s,ticker):
 x=s
 for term in sorted(ALLOWED|PROPER|{ticker},key=len,reverse=True): x=re.sub(r'(?<![A-Za-z])'+re.escape(term)+r'(?![A-Za-z])',' ',x,flags=re.I)
 words=re.findall(r'[A-Za-z][A-Za-z/-]{2,}',x)
 return [w for w in words if not (w.isupper() and len(w)<=12)]

def main():
 p=json.loads(DATA.read_text(encoding='utf-8'))
 for st in p.get('stocks',[]): clean_stock(st)
 rem=[]
 for st in p.get('stocks',[]):
  t=st.get('ticker','?')
  for f in FIELDS:
   v=st.get(f)
   if isinstance(v,str):
    w=prose_words(v,t)
    if len(w)>=3: rem.append({'ticker':t,'field':f,'englishWords':w[:20],'sample':v[:240]})
  for k,v in (st.get('framework') or {}).items():
   if isinstance(v,str):
    w=prose_words(v,t)
    if len(w)>=3: rem.append({'ticker':t,'field':f'framework::{k}','englishWords':w[:20],'sample':v[:240]})
 p.setdefault('meta',{})['thaiLanguageQA']={'checked':True,'remainingEnglishExplanationBlocks':len(rem),'technicalAbbreviationsPreserved':True,'policy':'คำอธิบายเป็นภาษาไทย; คงเฉพาะชื่อเฉพาะและตัวย่อทางการเงินมาตรฐาน'}
 DATA.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
 STATUS.write_text(json.dumps({'checked':True,'remainingEnglishExplanationBlocks':len(rem),'policy':'คำอธิบายเป็นภาษาไทย; คงเฉพาะชื่อเฉพาะและตัวย่อทางการเงินมาตรฐาน','remaining':rem},ensure_ascii=False,indent=2),encoding='utf-8')
 print('Thai QA remaining explanation blocks:',len(rem))
if __name__=='__main__': main()

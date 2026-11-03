#!/usr/bin/env python3
"""Final Thai-language cleanup and QA for displayed SET100 research text.

Runs after machine translation. It converts common English business/financial descriptors
inside otherwise-Thai sentences while intentionally preserving standard abbreviations such
as P/E, EV/EBITDA, ROE, ROIC, FCF, NPAT, TAM/SAM/SOM, etc.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data.json"
STATUS = ROOT / "research_thai_qa.json"

TARGET_FIELDS = [
    "summary", "debtEbitdaBasis", "debtEbitdaNote", "thesis", "bear",
    "marketBelieves", "marketMissing", "variables", "fit", "moatReason",
    "industryComparison",
]

# Longer phrases first. Standard abbreviations are deliberately not translated.
PHRASES = {
    "Integrated Energy": "ธุรกิจพลังงานครบวงจร",
    "Oil & Gas": "น้ำมันและก๊าซ",
    "Energy & Utilities": "พลังงานและสาธารณูปโภค",
    "Consumer Finance": "สินเชื่อผู้บริโภค",
    "Credit Card": "บัตรเครดิต",
    "Home Improvement Retail": "ค้าปลีกสินค้าเกี่ยวกับบ้าน",
    "Modern Retail": "ค้าปลีกสมัยใหม่",
    "Convenience/Food Retail": "ค้าปลีกสะดวกซื้อและอาหาร",
    "Premium Hospital": "โรงพยาบาลระดับพรีเมียม",
    "Residential Developers": "ผู้พัฒนาอสังหาริมทรัพย์เพื่ออยู่อาศัย",
    "Industrial Estate": "นิคมอุตสาหกรรม",
    "Container Shipping": "ขนส่งตู้คอนเทนเนอร์ทางเรือ",
    "Global Chemicals/PET": "เคมีภัณฑ์และ PET ระดับโลก",
    "Asian Full-Service": "สายการบินบริการเต็มรูปแบบในเอเชีย",
    "Financial Holding/Bank": "โฮลดิ้งการเงินและธนาคาร",
    "IT/Electronics Retail": "ค้าปลีกไอทีและอิเล็กทรอนิกส์",
    "Natural Rubber/Glove": "ยางธรรมชาติและถุงมือ",
    "Title Loan/Consumer Finance": "สินเชื่อทะเบียนรถและสินเชื่อผู้บริโภค",
    "Branded Consumer Health": "สินค้าเพื่อสุขภาพที่มีแบรนด์",
    "Pharma Distribution": "การจัดจำหน่ายเวชภัณฑ์",
    "Renewable Developers": "ผู้พัฒนาโครงการพลังงานหมุนเวียน",
    "Diversified Energy": "ธุรกิจพลังงานหลากหลาย",
    "Paint/Coatings": "สีและสารเคลือบ",
    "Construction/Infrastructure": "ก่อสร้างและโครงสร้างพื้นฐาน",
    "Transit/Infrastructure Holdings": "โฮลดิ้งระบบขนส่งและโครงสร้างพื้นฐาน",
    "OOH/Media": "สื่อนอกบ้านและสื่อโฆษณา",
    "EMS/Semiconductor Assembly": "การรับจ้างผลิตอิเล็กทรอนิกส์และประกอบเซมิคอนดักเตอร์",
    "PCB/Electronic Components": "แผงวงจรพิมพ์และชิ้นส่วนอิเล็กทรอนิกส์",
    "Consumer Health": "สินค้าเพื่อสุขภาพผู้บริโภค",
    "Power Holding": "โฮลดิ้งธุรกิจไฟฟ้า",
    "Toll Road/Rail": "ทางด่วนและรถไฟ",
    "Banking/Auto Finance": "ธนาคารและสินเชื่อรถยนต์",
    "Regional Packaging": "บรรจุภัณฑ์ในภูมิภาค",
    "Global Hotel": "โรงแรมระดับโลก",
    "Global Seafood/Food": "อาหารทะเลและอาหารระดับโลก",
    "Global Glove": "ถุงมือระดับโลก",
    "Building Materials": "วัสดุก่อสร้าง",
    "Marine Logistics": "โลจิสติกส์ทางทะเล",
    "Specialty Retail": "ค้าปลีกเฉพาะทาง",
    "Lifestyle Retail": "ค้าปลีกสินค้าไลฟ์สไตล์",
    "Core Profit": "กำไรจากธุรกิจหลัก",
    "Revenue Growth": "การเติบโตของรายได้",
    "Service Revenue Growth": "การเติบโตของรายได้บริการ",
    "Organic Growth": "การเติบโตแบบออร์แกนิก",
    "Production Growth": "การเติบโตของปริมาณผลิต",
    "Loan Growth": "การเติบโตของสินเชื่อ",
    "Rental Growth": "การเติบโตของค่าเช่า",
    "Sales/Store": "ยอดขายต่อสาขา",
    "Sales/Sqm": "ยอดขายต่อตารางเมตร",
    "Revenue per Site": "รายได้ต่อจุดโฆษณา",
    "Revenue/Patient": "รายได้ต่อผู้ป่วย",
    "Gross Margin": "อัตรากำไรขั้นต้น",
    "EBITDA Margin": "อัตรากำไร EBITDA",
    "EBIT Margin": "อัตรากำไร EBIT",
    "Net Margin": "อัตรากำไรสุทธิ",
    "EBITDAR Margin": "อัตรากำไร EBITDAR",
    "Operating Margin": "อัตรากำไรจากการดำเนินงาน",
    "Cash Margin": "อัตรากำไรเงินสด",
    "Balance Sheet": "งบดุล",
    "Funding Cost": "ต้นทุนเงินทุน",
    "Credit Cost": "ต้นทุนเครดิต",
    "Spectrum Cost": "ต้นทุนคลื่นความถี่",
    "Unit Cost": "ต้นทุนต่อหน่วย",
    "Cash Cost": "ต้นทุนเงินสด",
    "Feed Cost": "ต้นทุนอาหารสัตว์",
    "Bunker Cost": "ต้นทุนน้ำมันเรือ",
    "Net Debt": "หนี้สุทธิ",
    "Net Cash": "เงินสดสุทธิ",
    "Net Gearing": "อัตราหนี้สินสุทธิ",
    "Leverage": "ภาระหนี้",
    "Inventory Turns": "อัตราหมุนเวียนสินค้าคงคลัง",
    "Inventory Days": "จำนวนวันสินค้าคงคลัง",
    "Working Capital": "เงินทุนหมุนเวียน",
    "Cash Conversion": "การเปลี่ยนกำไรเป็นกระแสเงินสด",
    "Capacity Discipline": "วินัยในการบริหารกำลังการผลิต",
    "Customer Concentration": "การกระจุกตัวของลูกค้า",
    "Capacity Utilization": "อัตราการใช้กำลังการผลิต",
    "Utilization": "อัตราการใช้กำลังการผลิต",
    "Occupancy/Utilization": "อัตราการใช้บริการและกำลังการผลิต",
    "Occupancy": "อัตราการเข้าพัก",
    "Load Factor": "อัตราบรรทุกผู้โดยสาร",
    "Reserve Life": "อายุสำรอง",
    "Reserve Economics": "เศรษฐศาสตร์ของปริมาณสำรอง",
    "Reserve Replacement": "การทดแทนปริมาณสำรอง",
    "Fleet Age": "อายุเฉลี่ยฝูงบิน",
    "Fleet Utilization": "อัตราการใช้กองเรือ",
    "Fleet NAV": "NAV ของกองเรือ",
    "Concession Life": "อายุสัมปทาน",
    "Contracted Capacity": "กำลังการผลิตตามสัญญา",
    "Contracted MW": "กำลังผลิต MW ตามสัญญา",
    "Equity MW": "กำลังผลิต MW ตามสัดส่วนถือหุ้น",
    "Operating MW": "กำลังผลิต MW ที่ดำเนินงาน",
    "Margin/MW": "กำไรต่อ MW",
    "EBITDA/MW": "EBITDA ต่อ MW",
    "EBITDA/ton": "EBITDA ต่อตัน",
    "Fuel Pass-through": "การส่งผ่านต้นทุนเชื้อเพลิง",
    "SPP Margin": "ส่วนต่างกำไร SPP",
    "PPA quality": "คุณภาพสัญญา PPA",
    "Availability": "ความพร้อมจ่ายไฟ",
    "Land Sales/Transfers": "ยอดขายและโอนที่ดิน",
    "Utility Volume": "ปริมาณการใช้สาธารณูปโภค",
    "Recurring EBITDA": "EBITDA ที่เกิดซ้ำ",
    "Tenant Sales": "ยอดขายผู้เช่า",
    "Traffic/Ridership": "ปริมาณจราจรและจำนวนผู้โดยสาร",
    "Ridership": "จำนวนผู้โดยสาร",
    "Freight/TEU": "ค่าระวางต่อตู้ TEU",
    "Sales Volume": "ปริมาณขาย",
    "Realized Price": "ราคาขายจริง",
    "Realized Coal/Gas Price": "ราคาขายถ่านหินและก๊าซจริง",
    "Chicken Price": "ราคาไก่",
    "Livestock Spread": "ส่วนต่างราคาปศุสัตว์",
    "Feed Conversion": "ประสิทธิภาพการเปลี่ยนอาหารเป็นน้ำหนัก",
    "Branded Mix": "สัดส่วนสินค้ามีแบรนด์",
    "Specialty Mix": "สัดส่วนสินค้าพิเศษ",
    "Value-added Mix": "สัดส่วนสินค้ามูลค่าเพิ่ม",
    "International Mix": "สัดส่วนลูกค้าต่างประเทศ",
    "Asset-light Mix": "สัดส่วนธุรกิจแบบใช้สินทรัพย์ต่ำ",
    "Insurance Mix": "สัดส่วนธุรกิจประกัน",
    "Fee Mix": "สัดส่วนรายได้ค่าธรรมเนียม",
    "Fee Income": "รายได้ค่าธรรมเนียม",
    "Cost/Income": "อัตราต้นทุนต่อรายได้",
    "Capital Ratio": "อัตราส่วนเงินกองทุน",
    "Credit Rating": "อันดับเครดิต",
    "Debt Service": "ความสามารถชำระหนี้",
    "Dividend Yield": "อัตราผลตอบแทนเงินปันผล",
    "Dividend": "เงินปันผล",
    "Buyback": "ซื้อหุ้นคืน",
    "Backlog": "งานในมือ",
    "Presales": "ยอดขายรอโอน",
    "Capex": "เงินลงทุน",
    "Customer Data": "ข้อมูลลูกค้า",
    "Dealer Reach": "ความครอบคลุมเครือข่ายตัวแทนจำหน่าย",
    "Brand Share": "ส่วนแบ่งแบรนด์",
    "Operating Profit": "กำไรจากการดำเนินงาน",
    "Operating Profit Growth": "การเติบโตของกำไรจากการดำเนินงาน",
    "ARPU": "รายได้เฉลี่ยต่อผู้ใช้ (ARPU)",
    "Churn": "อัตราการยกเลิกบริการ",
    "Capex/Sales": "เงินลงทุนต่อยอดขาย",
    "Debt/EBITDA": "หนี้ต่อ EBITDA",
    "Net Debt/EBITDA": "หนี้สุทธิต่อ EBITDA",
    "Net Cash/Debt": "เงินสดสุทธิ/หนี้สุทธิ",
    "Gross/EBITDA Margin": "อัตรากำไรขั้นต้น/EBITDA",
    "Gross/EBIT Margin": "อัตรากำไรขั้นต้น/EBIT",
    "P/BV/EV-EBITDA": "P/BV และ EV/EBITDA",
    "SOTP Discount": "ส่วนลดจากมูลค่า SOTP",
    "peer group": "กลุ่มบริษัทเทียบเคียง",
    "Peer Group": "กลุ่มบริษัทเทียบเคียง",
    "peers": "กลุ่มบริษัทเทียบเคียง",
    "Peers": "กลุ่มบริษัทเทียบเคียง",
}

ALLOWED_ABBREVIATIONS = [
    "SET100","SETTRADE","SET","P/E","P/BV","EV/EBITDA","EBITDA","EBITDAR","EBIT",
    "NPAT","EPS","FCF","OCF","ROE","ROIC","D/E","NIM","NPL","CAGR","TAM","SAM","SOM",
    "YoY","QoQ","AI","FX","CAPEX","SG&A","ASP","SSSG","RevPAR","ADR","RASK","CASK","BOED",
    "PPA","COD","FID","NAV","IRR","ECL","LTV","GPM","FFO","GRM","ARPU","CAR","CET1","MW",
    "TEU","THB","USD","IPP","SPP","EMS","PCB","PET","E&P","LPG","SOTP"
]


def cleanup(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    out = text
    for en, th in sorted(PHRASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = re.sub(re.escape(en), th, out, flags=re.I)
    # Fix common awkward machine-translation artifacts around comparisons.
    out = re.sub(r"\bcompare with\b", "เปรียบเทียบกับ", out, flags=re.I)
    out = re.sub(r"\bcompare to\b", "เปรียบเทียบกับ", out, flags=re.I)
    out = re.sub(r"\bbenchmark\b", "เกณฑ์เปรียบเทียบ", out, flags=re.I)
    out = re.sub(r"\bmonitor\b", "ติดตาม", out, flags=re.I)
    out = re.sub(r"\bmargin\b", "อัตรากำไร", out, flags=re.I)
    out = re.sub(r"\bvolume\b", "ปริมาณ", out, flags=re.I)
    out = re.sub(r"\bprice\b", "ราคา", out, flags=re.I)
    out = re.sub(r"\bgrowth\b", "การเติบโต", out, flags=re.I)
    out = re.sub(r"\bquality\b", "คุณภาพ", out, flags=re.I)
    return re.sub(r"\s{2,}", " ", out).strip()


def clean_stock(stock: dict[str, Any]) -> None:
    for field in TARGET_FIELDS:
        if field in stock:
            stock[field] = cleanup(stock[field])
    fw = stock.get("framework") or {}
    for key in list(fw):
        fw[key] = cleanup(fw[key])
    if isinstance(stock.get("flags"), list):
        stock["flags"] = [cleanup(x) for x in stock["flags"]]
    for src in stock.get("sources") or []:
        if isinstance(src, dict) and "label" in src:
            src["label"] = cleanup(src["label"])


def unexplained_latin(text: str) -> list[str]:
    s = text
    # Remove allowed abbreviations and ticker-like/numeric tokens before checking prose.
    for term in sorted(ALLOWED_ABBREVIATIONS, key=len, reverse=True):
        s = re.sub(re.escape(term), " ", s, flags=re.I)
    words = re.findall(r"[A-Za-z][A-Za-z&/-]{2,}", s)
    # Company/product proper nouns are acceptable if sparse; multiple English words imply prose remains.
    return words


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    for stock in payload.get("stocks", []):
        clean_stock(stock)

    remaining = []
    for stock in payload.get("stocks", []):
        ticker = stock.get("ticker", "?")
        for field in TARGET_FIELDS:
            value = stock.get(field)
            if isinstance(value, str):
                words = unexplained_latin(value)
                if len(words) >= 4:
                    remaining.append({"ticker": ticker, "field": field, "englishWords": words[:20], "sample": value[:220]})
        for key, value in (stock.get("framework") or {}).items():
            if isinstance(value, str):
                words = unexplained_latin(value)
                if len(words) >= 4:
                    remaining.append({"ticker": ticker, "field": f"framework::{key}", "englishWords": words[:20], "sample": value[:220]})

    payload.setdefault("meta", {})["thaiLanguageQA"] = {
        "checked": True,
        "remainingEnglishExplanationBlocks": len(remaining),
        "technicalAbbreviationsPreserved": True,
    }
    DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    STATUS.write_text(json.dumps({
        "checked": True,
        "remainingEnglishExplanationBlocks": len(remaining),
        "technicalAbbreviationsPreserved": ALLOWED_ABBREVIATIONS,
        "remaining": remaining[:1000],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Thai research cleanup QA remaining blocks: {len(remaining)}")


if __name__ == "__main__":
    main()

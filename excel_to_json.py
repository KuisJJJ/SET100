#!/usr/bin/env python3
"""
Convert SET100 Master Excel -> data.json.

Design:
- Excel is the Source of Truth for research fields and Team Comment.
- Existing data.json remains the Source of Truth for auto-updated market fields
  (price, marketCap, P/E, P/BV, EV/EBITDA, SET Index).
- This prevents an Excel upload from overwriting fresher market data.
- New tickers can still be initialized from Excel when no existing JSON record exists.

No external Python packages are required.
"""

from pathlib import Path
from datetime import datetime, timezone
import json, re, sys, zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "SET100_Investment_Research_Master.xlsx"
OUT = ROOT / "data.json"

NS = {"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "pr":"http://schemas.openxmlformats.org/package/2006/relationships"}

def col_num(ref):
    m = re.match(r"([A-Z]+)", ref)
    n = 0
    for ch in m.group(1):
        n = n*26 + ord(ch)-64
    return n

def load_xlsx(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.findall(".//m:t", NS)))

    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rel_map = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall("pr:Relationship", NS)}
    sheets = {}
    for s in wb.findall("m:sheets/m:sheet", NS):
        rid = s.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rel_map[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        sheets[s.attrib["name"]] = target
    return z, shared, sheets

def cell_value(c, shared):
    t = c.attrib.get("t")
    if t == "inlineStr":
        return "".join(x.text or "" for x in c.findall(".//m:t", NS))
    v = c.find("m:v", NS)
    if v is None:
        return ""
    raw = v.text or ""
    if t == "s":
        try: return shared[int(raw)]
        except: return ""
    if t == "b":
        return raw == "1"
    try:
        num = float(raw)
        if num.is_integer(): return int(num)
        return num
    except:
        return raw

def read_sheet(z, shared, sheet_path):
    root = ET.fromstring(z.read(sheet_path))
    out = {}
    for row in root.findall(".//m:sheetData/m:row", NS):
        rnum = int(row.attrib["r"])
        vals = {}
        for c in row.findall("m:c", NS):
            vals[col_num(c.attrib["r"])] = cell_value(c, shared)
        out[rnum] = vals
    return out

def row_as_dict(rows, header_row=3):
    headers = rows.get(header_row, {})
    result = []
    for rnum in sorted(rows):
        if rnum <= header_row: continue
        row = rows[rnum]
        d = {}
        for cnum, head in headers.items():
            if head not in ("", None):
                d[str(head).strip()] = row.get(cnum, "")
        d["_row"] = rnum
        result.append(d)
    return result

def idx_by(rows, key="Ticker"):
    return {str(r.get(key,"")).strip(): r for r in rows if str(r.get(key,"")).strip()}

def fnum(v):
    if v in ("", None): return None
    try: return float(v)
    except: return None

def split_flags(v):
    return [x.strip() for x in str(v or "").split("|") if x.strip()]

if not MASTER.exists():
    raise SystemExit(f"Missing master workbook: {MASTER}")

existing = {}
if OUT.exists():
    existing = json.loads(OUT.read_text(encoding="utf-8"))

z, shared, sheets = load_xlsx(MASTER)

needed = ["01_Universe","02_Scorecard","03_Financials","04_Valuation","06_Deep_Research","07_Sources"]
tables = {}
for name in needed:
    if name not in sheets:
        raise SystemExit(f"Missing sheet: {name}")
    tables[name] = row_as_dict(read_sheet(z, shared, sheets[name]))

universe = idx_by(tables["01_Universe"])
score = idx_by(tables["02_Scorecard"])
fin = idx_by(tables["03_Financials"])
val = idx_by(tables["04_Valuation"])
deep = idx_by(tables["06_Deep_Research"])

sources = {}
for r in tables["07_Sources"]:
    t = str(r.get("Ticker","")).strip()
    url = str(r.get("URL","")).strip()
    label = str(r.get("Source Name","") or r.get("Source Type","")).strip()
    if t and url:
        sources.setdefault(t, []).append({"label":label or "Source","url":url})

existing_stocks = {s.get("ticker"): s for s in existing.get("stocks", []) if s.get("ticker")}
market_fields = ["price","marketCap","pe","pbv","evEbitda"]

stocks = []
for ticker, u in universe.items():
    d = deep.get(ticker)
    if not d:
        continue

    s = score.get(ticker, {})
    f = fin.get(ticker, {})
    v = val.get(ticker, {})
    old = existing_stocks.get(ticker, {})

    period_npat = fnum(f.get("Period NPAT (THB mn)"))
    prior_npat = fnum(f.get("Prior Period NPAT (THB mn)"))
    npat_growth = None
    if period_npat is not None and prior_npat not in (None, 0):
        npat_growth = round((period_npat/prior_npat - 1)*100, 1)

    record = {
        "rank": int(fnum(u.get("MCap Rank")) or 0),
        "ticker": ticker,
        "company": u.get("Company",""),
        "sector": u.get("Sector",""),
        "valuation": s.get("Valuation Class") or v.get("Conclusion",""),
        "period": f.get("Period",""),
        "qNpat": fnum(f.get("Quarter NPAT (THB mn)")),
        "periodNpat": period_npat,
        "npatGrowth": npat_growth,
        "debtEbitda": fnum(f.get("Debt / EBITDA (x)")),
        "debtEbitdaBasis": f.get("Debt/EBITDA Basis",""),
        "debtEbitdaNote": f.get("Debt/EBITDA Note",""),
        "score": fnum(s.get("Overall Score")),
        "flags": split_flags(s.get("Special Flags")),
        "summary": d.get("5-Minute Summary",""),
        "framework": {
            "1. Management": d.get("1. Management",""),
            "2. Product / Moat": d.get("2. Product / Moat",""),
            "3. TAM / Growth Runway": d.get("3. TAM / Growth Runway",""),
            "4. Positive Catalysts": d.get("4. Positive Catalysts",""),
            "5. Competitors": d.get("5. Competitors",""),
            "6. Revenue Growth & Margin": d.get("6. Revenue Growth & Margin",""),
            "7. Regulation": d.get("7. Regulation",""),
            "8. Narrative & Sentiment": d.get("8. Narrative & Sentiment",""),
            "9. Valuation Effect": d.get("9. Valuation Effect",""),
            "10. Earnings & Macro": d.get("10. Earnings & Macro",""),
            "11. Risk Radar": d.get("11. Risk Radar",""),
        },
        "thesis": d.get("Investment Thesis",""),
        "bear": d.get("Bear Thesis",""),
        "teamComment": d.get("Team Comment",""),
        "marketBelieves": d.get("What Market Believes",""),
        "marketMissing": d.get("What Market Might Be Missing",""),
        "variables": d.get("Key Variables",""),
        "fit": d.get("Investor Fit",""),
        "moatStatus": d.get("Moat: มี/ไม่มี",""),
        "moatReason": d.get("เหตุผล Moat",""),
        "industryComparison": d.get("Industry Comparison / Benchmark",""),
        "updateStatus": u.get("Update Status") or "Current",
        "marketDataUpdated": u.get("Market Data Updated",""),
        "financialDataUpdated": u.get("Financial Data Updated") or f.get("Period",""),
        "researchReviewed": u.get("Research Reviewed",""),
        "sources": sources.get(ticker, old.get("sources", [])),
    }

    # Preserve auto-market data if it already exists in data.json.
    for field in market_fields:
        if old.get(field) not in (None, ""):
            record[field] = old[field]
        else:
            excel_map = {
                "price": u.get("Price (THB)"),
                "marketCap": u.get("Market Cap (THB mn)"),
                "pe": v.get("P/E (x)"),
                "pbv": v.get("P/BV (x)"),
                "evEbitda": v.get("EV/EBITDA (x)"),
            }
            record[field] = fnum(excel_map[field])

    stocks.append(record)

stocks.sort(key=lambda x: x.get("rank", 999))

meta = dict(existing.get("meta", {}))
meta.update({
    "version": "v6",
    "masterWorkbook": MASTER.name,
    "companiesResearched": len(stocks),
    "totalUniverse": 100,
    "researchOrder": "Market Cap 100%",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
})

# Keep SET Index / market-series data untouched; only research/stocks are rebuilt.
out = {
    "meta": meta,
    "marketIndex": existing.get("marketIndex", {}),
    "stocks": stocks,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Generated {OUT.name}: {len(stocks)} researched stocks")

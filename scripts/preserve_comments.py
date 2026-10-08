#!/usr/bin/env python3
"""
Preserve shared Team Comments when a new research workbook is uploaded.

Rules:
- Nonblank Team Comment in new Excel -> use new text.
- Blank Team Comment -> restore previous text from team_comments.json.
- [[CLEAR]] -> intentionally clear the comment and remove it from backup.

The script edits only Team Comment cells in 06_Deep_Research, preserving cell styles.
No external Python packages are required.
"""
from pathlib import Path
import json, re, tempfile, zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "SET100_Investment_Research_Master.xlsx"
BACKUP = ROOT / "team_comments.json"

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m":NS_MAIN,"r":NS_REL,"pr":NS_PKG}
ET.register_namespace("", NS_MAIN)

def col_num(ref):
    m=re.match(r"([A-Z]+)",ref); n=0
    for ch in m.group(1): n=n*26+ord(ch)-64
    return n

def get_sheet_path(z, name):
    wb=ET.fromstring(z.read("xl/workbook.xml"))
    rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rel_map={r.attrib["Id"]:r.attrib["Target"] for r in rels.findall("pr:Relationship",NS)}
    for s in wb.findall("m:sheets/m:sheet",NS):
        if s.attrib["name"]==name:
            rid=s.attrib[f"{{{NS_REL}}}id"]
            t=rel_map[rid].lstrip("/")
            return t if t.startswith("xl/") else "xl/"+t
    raise RuntimeError(f"Missing sheet {name}")

def shared_strings(z):
    out=[]
    if "xl/sharedStrings.xml" not in z.namelist(): return out
    root=ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in root.findall("m:si",NS):
        out.append("".join(t.text or "" for t in si.findall(".//m:t",NS)))
    return out

def read_cell(c, shared):
    t=c.attrib.get("t")
    if t=="inlineStr": return "".join(x.text or "" for x in c.findall(".//m:t",NS))
    v=c.find("m:v",NS)
    if v is None: return ""
    raw=v.text or ""
    if t=="s":
        try:return shared[int(raw)]
        except:return ""
    return raw

def load_rows(z, sheet_path, shared):
    root=ET.fromstring(z.read(sheet_path))
    rows={}
    cells={}
    for row in root.findall(".//m:sheetData/m:row",NS):
        rnum=int(row.attrib["r"]); rows[rnum]={}
        for c in row.findall("m:c",NS):
            cnum=col_num(c.attrib["r"])
            rows[rnum][cnum]=read_cell(c,shared); cells[(rnum,cnum)]=c
    return root, rows, cells

def set_inline(c, text):
    ref=c.attrib.get("r")
    style=c.attrib.get("s")
    c.clear()
    if ref is not None: c.attrib["r"]=ref
    if style is not None: c.attrib["s"]=style
    c.attrib["t"]="inlineStr"
    isel=ET.SubElement(c,f"{{{NS_MAIN}}}is")
    t=ET.SubElement(isel,f"{{{NS_MAIN}}}t")
    if text.startswith(" ") or text.endswith(" "):
        t.attrib["{http://www.w3.org/XML/1998/namespace}space"]="preserve"
    t.text=text

def main():
    backup={}
    if BACKUP.exists():
        raw=json.loads(BACKUP.read_text(encoding="utf-8"))
        backup=raw.get("comments", raw) if isinstance(raw,dict) else {}

    with zipfile.ZipFile(MASTER,"r") as zin:
        spath=get_sheet_path(zin,"06_Deep_Research")
        shared=shared_strings(zin)
        root,rows,cells=load_rows(zin,spath,shared)
        headers=rows.get(3,{})
        ticker_col=next((c for c,v in headers.items() if str(v).strip()=="Ticker"),None)
        comment_col=next((c for c,v in headers.items() if str(v).strip()=="Team Comment"),None)
        if not ticker_col or not comment_col:
            raise RuntimeError("Ticker / Team Comment column not found")

        changed=False
        final_comments={}
        for rnum in sorted(rows):
            if rnum<=3: continue
            ticker=str(rows[rnum].get(ticker_col,"")).strip()
            if not ticker: continue
            current=str(rows[rnum].get(comment_col,"") or "")
            current_stripped=current.strip()

            if current_stripped=="[[CLEAR]]":
                desired=""
            elif current_stripped:
                desired=current
            else:
                desired=str(backup.get(ticker,"") or "")

            if desired:
                final_comments[ticker]=desired

            if desired != current:
                cell=cells.get((rnum,comment_col))
                if cell is None:
                    # find row element and insert a new cell with same row, preserving normal ordering
                    row_el=next(x for x in root.findall(".//m:sheetData/m:row",NS) if int(x.attrib["r"])==rnum)
                    def col_letters(n):
                        s=""
                        while n:
                            n,rem=divmod(n-1,26);s=chr(65+rem)+s
                        return s
                    cell=ET.Element(f"{{{NS_MAIN}}}c",{"r":f"{col_letters(comment_col)}{rnum}"})
                    row_el.append(cell)
                set_inline(cell,desired)
                changed=True

        BACKUP.write_text(json.dumps({"version":"v6.1","comments":final_comments},ensure_ascii=False,indent=2),encoding="utf-8")

        if changed:
            tmp=MASTER.with_suffix(".tmp.xlsx")
            with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename==spath:
                        zout.writestr(item,ET.tostring(root,encoding="utf-8",xml_declaration=True))
                    else:
                        zout.writestr(item,zin.read(item.filename))
            tmp.replace(MASTER)
            print("Restored/preserved Team Comments in Master Excel.")
        else:
            print("No Team Comment restoration needed.")

if __name__=="__main__":
    main()

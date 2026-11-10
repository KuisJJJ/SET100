#!/usr/bin/env python3
"""Sync verified numeric facts/dates to Master; never rewrite research/scores.

Requires openpyxl. Run explicitly after a reviewed refresh, not on every quote.
"""
import json
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT/'data.json').read_text())
    stocks = {s['ticker']:s for s in data['stocks']}
    path = ROOT/'SET100_Investment_Research_Master.xlsx'
    wb = openpyxl.load_workbook(path)
    for sheet, mapping in {
        '01_Universe': {'MCap Rank':'rank', 'Price (THB)':'price', 'Market Cap (THB mn)':'marketCap',
                        'Financial Period':'period', 'Financial Data Updated':'period',
                        'Update Status':'updateStatus','Market Data Updated':'marketDataAsOf',
                        'Market Date':'marketDataAsOf', 'Financial Period End':'financialPeriodEnd',
                        'Financial Checked At':'financialCheckedAt', 'Financial Assurance':'financialAssurance',
                        'Financial Source URL':'financialSourceUrl', 'Research Financial Period':'researchFinancialPeriod'},
        '03_Financials': {'Period':'period','Quarter NPAT (THB mn)':'qNpat','Period NPAT (THB mn)':'periodNpat',
                          'Prior Period NPAT (THB mn)':'priorPeriodNpat','NPAT YoY':'npatGrowth',
                          'Source':'financialSourceUrl','Financial Period End':'financialPeriodEnd',
                          'Financial Assurance':'financialAssurance', 'Financial Checked At':'financialCheckedAt'},
        '04_Valuation': {'Price (THB)':'price','Market Cap (THB mn)':'marketCap','P/E (x)':'pe',
                         'P/BV (x)':'pbv','Data Date':'valuationRatiosAsOf',
                         'Price As Of':'marketDataAsOf'}
    }.items():
        ws = wb[sheet]
        columns = {c.value:c.column for c in ws[3] if c.value}
        for header in mapping:
            if header not in columns:
                col = ws.max_column+1
                ws.cell(3,col,header)
                columns[header] = col
        for row in range(4,ws.max_row+1):
            t = str(ws.cell(row,columns['Ticker']).value or '').strip()
            s = stocks.get(t)
            if not s:continue
            for header,key in mapping.items():
                if key in s:ws.cell(row,columns[header]).value = s[key]
            if sheet == '03_Financials':
                # Other metrics may remain on the structured source's older period.
                for header,key in [('Revenue (THB mn)','financialRevenue'),('EBITDA (THB mn)','financialEbitda'),('EPS / Share','financialEps')]:
                    ws.cell(row,columns[header]).value = s.get(key) if s.get('financialMetricsPeriodEnd') == s.get('financialPeriodEnd') else None
                ws.cell(row,columns['Note']).value = ('ข้อมูลกำไรจาก '+s.get('financialSource','')+'; สิ้นสุด '+s.get('financialPeriodEnd','ไม่ระบุ')+
                    '; '+s.get('financialAssurance','')+'; หนี้/EBITDA และบทวิเคราะห์ยังเป็นชุด '+s.get('researchFinancialPeriod','เดิม'))
                # Original workbook growth is a percent-formatted fraction.
                ws.cell(row,columns['NPAT YoY']).value = s['npatGrowth']/100 if s.get('npatGrowth') is not None else None
    wb.save(path)
    print(f'Synchronized dated facts for {len(stocks)} companies; research and scores preserved.')


if __name__ == '__main__':main()

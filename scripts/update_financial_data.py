#!/usr/bin/env python3
"""Refresh dated financial/quote facts, keeping human research separately dated.

No invented Q3 labels: only accept structured source periods or validated F45.
Failed reads retain last verified values and become visible pending statuses.
"""
import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re

from settrade_source import fetch_stock, fetch_news, fetch_f45

ROOT = Path(__file__).resolve().parents[1]
BKK = timezone(timedelta(hours=7))
MONTHS = {'มกราคม': 1, 'กุมภาพันธ์': 2, 'มีนาคม': 3, 'เมษายน': 4,
          'พฤษภาคม': 5, 'มิถุนายน': 6, 'กรกฎาคม': 7, 'สิงหาคม': 8,
          'กันยายน': 9, 'ตุลาคม': 10, 'พฤศจิกายน': 11, 'ธันวาคม': 12}
FACT_FIELDS = ['period', 'qNpat', 'periodNpat', 'priorPeriodNpat', 'quarterPriorNpat',
               'npatGrowth', 'npatGrowthBasis', 'financialPeriodStart', 'financialPeriodEnd',
               'financialDataUpdated', 'financialSource', 'financialSourceUrl',
               'financialPublishedAt', 'financialAssurance', 'financialCheckedAt',
               'latestAvailablePeriod', 'latestAvailablePeriodEnd', 'latestFinancialSourceUrl',
               'financialCheckStatus', 'financialCheckError', 'updateStatus',
               'researchFinancialPeriod', 'researchPeriodEnd', 'researchNeedsReview',
               'valuationAsOf', 'debtEbitdaAsOf', 'financialRevenue', 'financialEbitda',
               'financialEps', 'financialMetricsPeriodEnd', 'financialSourceRecord']


def num(v):
    return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)


def growth(current, prior):
    # A negative/zero base does not have a meaningful conventional growth %.
    return round((current / prior - 1) * 100, 2) if num(current) and num(prior) and prior > 0 else None


def target_period_end(today):
    month = ((today.month - 1) // 3) * 3
    year = today.year
    if month == 0:
        month, year = 12, year - 1
    return f'{year}-{month:02d}-{calendar.monthrange(year, month)[1]}'


def research_end(stock):
    label = stock.get('researchFinancialPeriod') or stock.get('period', '')
    year = re.search(r'20\d\d', label)
    q = re.search(r'Q([1-4])', label)
    if not year or not q:
        return None
    y, month = int(year[0]), int(q[1])*3
    # Existing workbook labels use fiscal year ending in the named year.
    offsets = {'AOT': 3, 'BTS': 9, 'VGI': 9, 'AEONTS': 10}
    month -= offsets.get(stock['ticker'], 0)
    if month <= 0:
        month += 12
        y -= 1
    return f'{y}-{month:02d}-{calendar.monthrange(y, month)[1]}'


def period_label(quarter, year):
    q = {'6M': 'Q2', '9M': 'Q3', 'YE': 'FY', 'Q9': 'FY'}.get(quarter, quarter)
    months = {'Q1': 3, '6M': 6, '9M': 9, 'YE': 12, 'Q9': 12}.get(quarter)
    return f'{q} FY{year}' + (f' / สะสม {months} เดือน' if months else '')


def parse_f45(d, today):
    text = d.get('content') or ''
    published = datetime.fromisoformat(d['datetime'])
    if published.date() > today or not re.search(r'สำหรับงบการเงินรวม|งบการเงินรวม', text):
        raise ValueError('F45 is future-dated or not identified as consolidated')
    qm = re.search(r'ไตรมาสที่\s*([1-4])', d['headline'])
    if qm and qm[1] == '1':
        raise ValueError('Q1 F45 uses single-period layout; structured Q1 retained')
    dates = re.search(r'สิ้นสุดวันที่\s*(\d{1,2})\s+(' + '|'.join(MONTHS) + ')', text)
    years = re.search(r'\nปี\s+(25\d\d)\s+(25\d\d)\s+(25\d\d)\s+(25\d\d)', text)
    unit = re.search(r'หน่วย\s*:\s*(พันบาท|ล้านบาท|บาท)', text)
    token = r'(?:\(?-?\d[\d,]*(?:\.\d+)?\)?)'
    profit = re.search(r'กำไร\s*\(ขาดทุน\)[^\d\n]*(' + token + r')\s+(' + token + r')\s+(' + token + r')\s+(' + token + r')', text)
    if not all((qm, dates, years, unit, profit)):
        raise ValueError('Unsupported F45 layout; retained verified values')
    if years[1] != years[3] or years[2] != years[4] or int(years[1]) - int(years[2]) != 1:
        raise ValueError('F45 comparison years do not match')
    month, day = MONTHS[dates[2]], int(dates[1])
    end_year = published.year - (month > published.month)
    end = datetime(end_year, month, day).date().isoformat()
    factor = {'พันบาท': 1000, 'ล้านบาท': 1, 'บาท': 1_000_000}[unit[1]]
    def amount(s):
        return float(s.replace(',', '').replace('(', '-').replace(')', '')) / factor
    q, pq, ytd, pytd = map(amount, profit.groups())
    quarter = int(qm[1])
    return {'period': period_label({1:'Q1',2:'6M',3:'9M',4:'YE'}[quarter], int(years[1])-543),
            'financialPeriodEnd': end, 'qNpat': q, 'quarterPriorNpat': pq,
            'periodNpat': ytd, 'priorPeriodNpat': pytd,
            'financialSourceUrl': d['sourceUrl'], 'financialSource': 'SET F45 ผ่าน Settrade (งบรวม)',
            'financialPublishedAt': d['datetime'],
            'financialAssurance': 'ก่อนสอบทาน' if 'ก่อนสอบทาน' in d['headline'] else 'สอบทานแล้ว',
            'financialSourceRecord': {'quarter': quarter, 'fiscalYear': int(years[1])-543,
                                      'sourceUnit': unit[1], 'netProfitValues': list(profit.groups())}}


def structured_facts(snapshot, today):
    f = snapshot['financial']
    rows = [r for r in f.get('financialDataAccumulatedChart', [])
            if r.get('fsType') in ('C', 'E', 'U') and r.get('endDate', '')[:10] <= today.isoformat()
            and num(r.get('netProfit'))]
    if not rows:
        raise ValueError('No usable consolidated financial series')
    consolidated = [r for r in rows if r.get('fsType') == 'C']
    rows = consolidated or rows
    a = max(rows, key=lambda r: r['endDate'])
    end = a['endDate'][:10]
    q = next((r for r in f.get('financialDataQuarterChart', [])
              if r.get('endDate', '')[:10] == end and r.get('fsType') == a['fsType']), None)
    if not q or not num(q.get('netProfit')):
        raise ValueError('Quarterly and accumulated periods do not match')
    prior = next((r for r in rows if r['quarter'] == a['quarter'] and r['year'] == a['year']-1), {})
    pq = next((r for r in f.get('financialDataQuarterChart', [])
               if r.get('quarter') == q['quarter'] and r.get('year') == q['year']-1 and r.get('fsType') == a['fsType']), {})
    return {'period': period_label(a['quarter'], a['year']), 'financialPeriodEnd': end,
            'financialPeriodStart': a['beginDate'][:10],
            'qNpat': q['netProfit']/1000, 'periodNpat': a['netProfit']/1000,
            'priorPeriodNpat': prior['netProfit']/1000 if num(prior.get('netProfit')) else None,
            'quarterPriorNpat': pq['netProfit']/1000 if num(pq.get('netProfit')) else None,
            'financialRevenue': a['totalRevenue']/1000 if num(a.get('totalRevenue')) else None,
            'financialEbitda': a['ebitda']/1000 if num(a.get('ebitda')) else None,
            'financialEps': a.get('eps'), 'financialMetricsPeriodEnd': end,
            'financialSource': 'SET / Settrade (' + {'C':'งบรวม','E':'วิธีส่วนได้เสีย','U':'งบเฉพาะกิจการ'}[a['fsType']] + '; หน่วยต้นทางพันบาท)',
            'financialSourceUrl': snapshot['sourceUrl'], 'financialAssurance': 'ไม่ระบุสถานะสอบทานในข้อมูลสรุป (ดูงบต้นฉบับ)',
            'financialPublishedAt': None,
            'financialSourceRecord': {k:a.get(k) for k in ('symbol','quarter','year','beginDate','endDate','netProfit','fsType')}}


def apply_snapshot(stock, snapshot, news, checked):
    today = datetime.fromisoformat(checked).date()
    facts = structured_facts(snapshot, today)
    errors = []
    for f45 in news.get('f45', []):
        try:
            candidate = parse_f45(f45, today)
            if (candidate['financialPeriodEnd'], candidate.get('financialPublishedAt') or '') > (facts['financialPeriodEnd'], facts.get('financialPublishedAt') or ''):
                # A newer F45 supplies profits only, never relabel old revenue/EBITDA.
                if candidate['financialPeriodEnd'] > facts['financialPeriodEnd']:
                    facts['financialPeriodStart'] = None
                facts.update(candidate)
        except (ValueError, KeyError, TypeError) as e:
            if not str(e).startswith('Q1 F45'):
                errors.append(str(e))
    # Do not roll back a previously verified later period when source lags.
    if stock.get('financialPeriodEnd', '') > facts['financialPeriodEnd']:
        facts = {k: stock[k] for k in FACT_FIELDS if k in stock}
    elif (stock.get('financialPeriodEnd') == facts['financialPeriodEnd']
          and stock.get('financialPublishedAt') and not facts.get('financialPublishedAt')
          and abs(stock.get('periodNpat', 0)-facts['periodNpat']) < .01):
        # A known F45 remains a valid publication source when it leaves the news list.
        for key in ('financialPublishedAt', 'financialAssurance', 'financialSource', 'financialSourceUrl'):
            facts[key] = stock[key]
    stock.setdefault('researchFinancialPeriod', stock.get('period', 'ไม่ระบุงวด'))
    if not stock.get('researchPeriodEnd'):
        stock['researchPeriodEnd'] = research_end(stock)
    stock.setdefault('valuationAsOf', stock.get('researchReviewed'))
    stock.setdefault('debtEbitdaAsOf', stock.get('period'))
    stock.update(facts)
    stock['financialDataUpdated'] = facts['period']
    stock['financialCheckedAt'] = checked
    stock['npatGrowth'] = growth(stock['periodNpat'], stock.get('priorPeriodNpat'))
    stock['npatGrowthBasis'] = 'กำไรสะสมเทียบงวดเดียวกันปีก่อน; ไม่แสดง % หากฐานปีก่อนเป็นศูนย์หรือติดลบ'
    stock['latestAvailablePeriod'] = facts['period']
    stock['latestAvailablePeriodEnd'] = facts['financialPeriodEnd']
    stock['latestFinancialSourceUrl'] = facts['financialSourceUrl']
    stock['financialCheckStatus'] = 'verified' if not errors else 'partial'
    stock['financialCheckError'] = '; '.join(errors) if errors else None
    stock['researchNeedsReview'] = stock['financialPeriodEnd'] > (stock.get('researchPeriodEnd') or '')
    stock['updateStatus'] = 'Research Needs Update' if stock['researchNeedsReview'] else 'Verified Financials'
    target_end = target_period_end(today)
    if stock['financialPeriodEnd'] < target_end:
        stock['updateStatus'] = 'Awaiting New Results'
    # A filing announcement can precede structured numeric data. Surface this gap.
    for n in news.get('news', []):
        title = n.get('title', '')
        published = n.get('publishDate', '')
        newer_september = target_end == '2026-09-30' and re.search(r'สิ้นสุด.*30\s*(?:กันยายน|ก\.ย\.).*2569', title)
        if newer_september and published[:10] <= today.isoformat() and stock['financialPeriodEnd'] < target_end:
            stock['latestAvailablePeriod'] = 'งวดสิ้นสุด 30/09/2569 (พบประกาศ; ตัวเลขรอตรวจสอบ)'
            stock['latestAvailablePeriodEnd'] = '2026-09-30'
            stock['latestFinancialSourceUrl'] = n['url']
            stock['updateStatus'] = 'New Results Available'
            stock['financialCheckStatus'] = 'partial'
    quote = snapshot['quote']
    asof = quote.get('marketDateTime', '')
    # Source timestamps, not refresh timestamps, determine freshness.
    if asof and asof[:10] >= stock.get('marketDataUpdated', '')[:10] and num(quote.get('last')) and quote['last'] > 0:
        stock['price'] = quote['last']
        stock['marketDataUpdated'] = asof[:10]
        stock['marketDataAsOf'] = asof
        stock['marketDataProvider'] = 'SET / Settrade'
        stock['marketSourceUrl'] = snapshot['sourceUrl']
        if num(quote.get('listedShare')) and quote['listedShare'] > 0:
            stock['marketCap'] = round(quote['last'] * quote['listedShare'] / 1_000_000, 2)
            stock['marketCapBasis'] = 'ราคา × จำนวนหุ้นจดทะเบียน จาก SET / Settrade'
    stats_date = quote.get('statisticsAsOf')
    if stats_date:
        stock['valuationRatiosAsOf'] = stats_date
        stock['pe'], stock['pbv'] = quote.get('peRatio'), quote.get('pbRatio')
        stock['valuationFinancialPeriodEnd'] = max((r.get('financialDate','')[:10] for r in snapshot['financial'].get('tradingStat', []) if r.get('date','')[:10] == stats_date[:10]), default=None)
    return errors


def get_sources(ticker):
    snapshot = fetch_stock(ticker)
    news = {'news': [], 'f45': []}
    try:
        news['news'] = fetch_news(ticker)
        for n in news['news']:
            if 'F45' in n.get('title', ''):
                news['f45'].append(fetch_f45(ticker, n['uuid']))
    except Exception as e:
        news['error'] = str(e)
    return snapshot, news


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ticker', default='')
    ap.add_argument('--snapshot-dir', type=Path)
    ap.add_argument('--news-dir', type=Path)
    args = ap.parse_args()
    data = json.loads((ROOT/'data.json').read_text())
    checked = datetime.now(BKK).isoformat(timespec='seconds')
    saved_path = ROOT/'financial_snapshots.json'
    saved = json.loads(saved_path.read_text()) if saved_path.exists() else {}
    failures, results = [], []
    stocks = [s for s in data['stocks'] if not args.ticker or s['ticker'] == args.ticker.upper()]
    def sources(s):
        t = s['ticker']
        if args.snapshot_dir:
            return json.loads((args.snapshot_dir/(t+'.json')).read_text()), json.loads((args.news_dir/(t+'.json')).read_text())
        return get_sources(t)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(sources, s):s for s in stocks}
        for future in as_completed(pending):
            s = pending[future]
            try:
                snapshot, news = future.result()
                warnings = apply_snapshot(s, snapshot, news, checked)
                if news.get('error'):
                    s['financialCheckStatus'] = 'partial'
                    s['financialCheckError'] = news['error']
                saved[s['ticker']] = {k:s[k] for k in FACT_FIELDS if k in s}
                results.append({'ticker': s['ticker'], 'period': s['period'], 'endDate': s['financialPeriodEnd'],
                                'source': s['financialSourceUrl'], 'assurance': s['financialAssurance'],
                                'checkStatus': s['financialCheckStatus'], 'warnings': warnings})
                print(f"{s['ticker']}: {s['period']} ending {s['financialPeriodEnd']} ({s['financialCheckStatus']})", flush=True)
            except Exception as e:
                s['financialCheckStatus'], s['financialCheckError'] = 'failed', str(e)
                s['updateStatus'] = 'Verification Pending'
                failures.append({'ticker':s['ticker'], 'error':str(e)})
                print(f"{s['ticker']}: source check failed; retaining saved facts", flush=True)
    if not args.ticker and len(stocks) == 100 and not failures:
        data['stocks'].sort(key=lambda s:s.get('marketCap') or 0, reverse=True)
        for i,s in enumerate(data['stocks'],1):s['rank'] = i
    meta = data['meta']
    meta['financialCheckedAt'] = checked
    meta['financialDataUpdated'] = 'แสดงงวดและวันสิ้นงบแยกรายบริษัท'
    target_end = target_period_end(datetime.fromisoformat(checked).date())
    meta['financialTargetPeriodEnd'] = target_end
    meta['financialCoverage'] = {'checked':sum(bool(s.get('financialCheckedAt')) for s in data['stocks']),
                                 'checkedThisRun':len(results), 'failed':len(failures),
                                 'septemberOrLater':sum(s.get('financialPeriodEnd','') >= target_end for s in data['stocks'])}
    meta['marketDataUpdated'] = max((s.get('marketDataAsOf') or s.get('marketDataUpdated') or '' for s in data['stocks']), default='')
    meta['generatedAt'] = checked
    meta['financialUpdatePolicy'] = 'อัปเดตข้อเท็จจริงจาก SET/Settrade และ F45; คงวันที่และงวดของบทวิเคราะห์เดิม; ไม่สร้างงบที่ยังไม่มีหลักฐาน'
    report = {'checkedAt':checked, 'targetPeriodEnd':target_end, 'results':sorted(results,key=lambda r:r['ticker']), 'failures':failures}
    for path, value in [('data.json',data),('financial_snapshots.json',saved),('financial_update_status.json',report)]:
        (ROOT/path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print(json.dumps(meta['financialCoverage']))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'data.json'
STATUS_FILE = ROOT / 'update_status.json'
BKK = timezone(timedelta(hours=7))
SET100_PAGE = 'https://www.set.or.th/en/market/index/set100/overview'
UA = 'Mozilla/5.0 (compatible; SET100ResearchUpdater/1.1)'

# IMPORTANT DATA POLICY
# - Research ranking is NOT recalculated from researched stocks only.
#   Until the system stores market cap for all 100 SET100 constituents, doing so
#   would create a false rank because unresearched constituents are missing.
# - Automatic updater changes market fields only: price, marketCap,
#   marketDataUpdated/provider and universe validation.
# - Research intelligence and research-rank snapshot remain protected.

def get_json(url, timeout=20):
    req=Request(url, headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*'})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def get_text(url, timeout=20):
    req=Request(url, headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml'})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8','ignore')

def yahoo_latest(ticker):
    """Fallback quote source. It is explicitly labelled as secondary data."""
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.BK?range=5d&interval=1d'
    j=get_json(url)
    res=(j.get('chart') or {}).get('result') or []
    if not res: return None
    r=res[0]; meta=r.get('meta') or {}
    px=meta.get('regularMarketPrice'); ts=meta.get('regularMarketTime')
    if px is None:
        closes=(((r.get('indicators') or {}).get('quote') or [{}])[0].get('close') or [])
        closes=[x for x in closes if x is not None]
        px=closes[-1] if closes else None
    if px is None: return None
    dt=datetime.fromtimestamp(ts,timezone.utc).astimezone(BKK) if ts else datetime.now(BKK)
    return {'price':float(px),'asof':dt.isoformat(timespec='seconds'),'provider':'Yahoo Finance (.BK) secondary fallback'}

def parse_set100_from_html():
    html=get_text(SET100_PAGE)
    # First try symbols that appear in constituent-table context. The SET page is
    # dynamic, so keep conservative validation and never overwrite the universe.
    candidates=re.findall(r'(?:>|&quot;|\")([A-Z][A-Z0-9&.-]{1,11})(?:<|&quot;|\")', html)
    stop={'SET','SET50','SET100','SET50FF','SET100FF','HTML','HEAD','BODY','HTTP','HTTPS','OPEN','HIGH','LOW','LAST','CHANGE','OFFER','VALUE','VOLUME'}
    out=[]
    for c in candidates:
        c=re.sub(r'[^A-Z0-9&.-]','',c.upper())
        if c and c not in stop and c not in out:
            out.append(c)
    # A valid scrape should be close to 100; reject ambiguous HTML rather than
    # producing a false membership alert.
    return out if 95 <= len(out) <= 105 else []

def duplicates(stocks):
    seen=set(); dup=[]
    for s in stocks:
        t=str(s.get('ticker','')).upper().strip()
        if not t: continue
        if t in seen and t not in dup: dup.append(t)
        seen.add(t)
    return dup

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--ticker',default=''); args=ap.parse_args()
    payload=json.loads(DATA_FILE.read_text(encoding='utf-8'))
    stocks=payload.get('stocks',[]); target=args.ticker.strip().upper(); now=datetime.now(BKK)
    updated=0; failures=[]; logs=[]

    for s in stocks:
        if target and str(s.get('ticker','')).upper()!=target: continue
        t=str(s.get('ticker','')).upper(); old_px=s.get('price'); old_mc=s.get('marketCap')
        try:
            q=yahoo_latest(t)
            if not q: raise RuntimeError('no quote')
            # Preserve implied listed shares from the research snapshot. This is
            # suitable for routine quote refreshes, but corporate actions should
            # trigger a manual share-count review.
            shares=(float(old_mc)/float(old_px)) if old_px and old_mc and float(old_px)>0 else None
            s['price']=round(q['price'],4)
            if shares:
                s['marketCap']=round(shares*q['price'],2)
            s['marketDataUpdated']=q['asof'][:10]
            s['marketDataProvider']=q['provider']
            updated+=1; logs.append(f"{t}: {old_px} -> {s['price']}")
            time.sleep(0.05)
        except Exception as e:
            failures.append({'ticker':t,'error':str(e)})

    official=[]; universe_error=None
    try:
        official=parse_set100_from_html()
        if not official:
            universe_error='Official SET100 HTML could not be parsed reliably; membership was NOT changed.'
    except Exception as e:
        universe_error=f'Official SET100 check failed: {e}'

    researched=[str(s.get('ticker','')).upper().strip() for s in stocks if s.get('ticker')]
    dup=duplicates(stocks)
    researched_set=set(researched)

    if official:
        off=set(official)
        outside=sorted(researched_set-off)
        missing_research=sorted(off-researched_set)
        uv={
            'ok':not(outside or dup),
            'checkedAt':now.isoformat(timespec='seconds'),
            'officialCount':len(off),
            'researchedCount':len(researched_set),
            'coveragePct':round(len(researched_set & off)/len(off)*100,1) if off else None,
            'researchedOutsideOfficialUniverse':outside,
            'notYetResearched':missing_research,
            'duplicates':dup,
            'source':SET100_PAGE,
            'note':'Missing research is expected until coverage reaches 100/100; it is not a universe error.'
        }
    else:
        uv={
            'ok':False,
            'checkedAt':now.isoformat(timespec='seconds'),
            'officialCount':None,
            'researchedCount':len(researched_set),
            'coveragePct':None,
            'researchedOutsideOfficialUniverse':[],
            'notYetResearched':[],
            'duplicates':dup,
            'source':SET100_PAGE,
            'error':universe_error
        }

    meta=payload.setdefault('meta',{})
    meta['version']='v7-safe-update'
    meta['companiesResearched']=len(researched_set)
    meta['marketDataUpdated']=now.strftime('%Y-%m-%d %H:%M')
    meta['generatedAt']=now.isoformat(timespec='seconds')
    meta['universeValidation']=uv
    meta['rankPolicy']='Research rank remains the validated snapshot rank until market caps for all 100 SET100 constituents are available.'
    meta['automaticUpdatePolicy']={
        'autoFields':['price','marketCap','marketDataUpdated','marketDataProvider','universeValidation'],
        'protectedResearchFields':['rank','valuation','score','framework','thesis','bear','moatStatus','moatReason','marketBelieves','marketMissing','variables','fit','teamComment'],
        'note':'Automatic updater never rewrites research intelligence or ranks from a partial researched universe.'
    }
    payload['stocks']=stocks
    DATA_FILE.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    status={
        'generatedAt':now.isoformat(timespec='seconds'),
        'target':target or 'ALL',
        'updatedStocks':updated,
        'failures':failures,
        'universeValidation':uv,
        'logs':logs[-100:]
    }
    STATUS_FILE.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'data.json'
STATUS_FILE = ROOT / 'update_status.json'
LOCKED_UNIVERSE_FILE = ROOT / 'official_set100.json'
BKK = timezone(timedelta(hours=7))
SET100_PAGE = 'https://www.set.or.th/en/market/index/set100/overview'
UA = 'Mozilla/5.0 (compatible; SET100ResearchUpdater/1.3)'

# DATA POLICY
# - Research intelligence is always protected.
# - Routine quote refresh updates price / market cap only.
# - Rank is recalculated ONLY when an Update All run successfully refreshes all
#   100 unique researched constituents. A single-ticker update never changes rank.
# - Live official-universe parsing is attempted first. If SET dynamic HTML cannot
#   be parsed reliably, a dated locked official snapshot is used as a transparent
#   fallback; it never silently changes membership.

def get_json(url, timeout=20):
    req=Request(url, headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*'})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def get_text(url, timeout=20):
    req=Request(url, headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml'})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8','ignore')

def yahoo_latest(ticker):
    """Secondary fallback quote source; every record is explicitly labelled."""
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
    candidates=re.findall(r'(?:>|&quot;|\")([A-Z][A-Z0-9&.-]{1,11})(?:<|&quot;|\")', html)
    stop={'SET','SET50','SET100','SET50FF','SET100FF','HTML','HEAD','BODY','HTTP','HTTPS','OPEN','HIGH','LOW','LAST','CHANGE','OFFER','VALUE','VOLUME'}
    out=[]
    for c in candidates:
        c=re.sub(r'[^A-Z0-9&.-]','',c.upper())
        if c and c not in stop and c not in out:
            out.append(c)
    return out if 95 <= len(out) <= 105 else []

def locked_official_universe():
    if not LOCKED_UNIVERSE_FILE.exists():
        return [], {}
    try:
        raw=json.loads(LOCKED_UNIVERSE_FILE.read_text(encoding='utf-8'))
        tickers=[str(x).upper().strip() for x in raw.get('tickers',[]) if str(x).strip()]
        return tickers, raw
    except Exception:
        return [], {}

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

    researched=[str(s.get('ticker','')).upper().strip() for s in stocks if s.get('ticker')]
    dup=duplicates(stocks); researched_set=set(researched)

    # Universe validation: live SET scrape first, then dated locked official list.
    official=[]; official_mode='live_set_html'; official_meta={}; universe_error=None
    try:
        official=parse_set100_from_html()
    except Exception as e:
        universe_error=f'Live SET100 check failed: {e}'
    if not official:
        locked, locked_meta=locked_official_universe()
        if locked:
            official=locked; official_mode='locked_official_snapshot'; official_meta=locked_meta
        else:
            universe_error=universe_error or 'Official SET100 HTML could not be parsed and no locked universe is available.'

    if official:
        off=set(official)
        outside=sorted(researched_set-off); missing_research=sorted(off-researched_set)
        uv={
            'ok':not(outside or dup) and len(off)==100,
            'checkedAt':now.isoformat(timespec='seconds'),
            'validationMode':official_mode,
            'officialCount':len(off),
            'researchedCount':len(researched_set),
            'coveragePct':round(len(researched_set & off)/len(off)*100,1) if off else None,
            'researchedOutsideOfficialUniverse':outside,
            'notYetResearched':missing_research,
            'duplicates':dup,
            'source': official_meta.get('source') if official_mode=='locked_official_snapshot' else SET100_PAGE,
            'officialPeriod': official_meta.get('period') if official_mode=='locked_official_snapshot' else None,
            'officialValidatedAt': official_meta.get('validatedAt') if official_mode=='locked_official_snapshot' else None,
            'note':'Locked snapshot is a transparent fallback when SET dynamic HTML cannot be parsed; refresh it when SET announces a new constituent period.'
        }
    else:
        uv={
            'ok':False,'checkedAt':now.isoformat(timespec='seconds'),'validationMode':'unavailable',
            'officialCount':None,'researchedCount':len(researched_set),'coveragePct':None,
            'researchedOutsideOfficialUniverse':[],'notYetResearched':[],'duplicates':dup,
            'source':SET100_PAGE,'error':universe_error
        }

    # With complete coverage, a successful Update All can safely make rank current.
    rank_recalculated=False
    all_quotes_complete=(not target and len(stocks)==100 and len(researched_set)==100 and updated==100 and not failures)
    if all_quotes_complete and all(s.get('marketCap') not in (None,'') for s in stocks):
        stocks.sort(key=lambda x: float(x.get('marketCap') or 0), reverse=True)
        for i,s in enumerate(stocks,1):
            s['rank']=i
        rank_recalculated=True
        logs.append('Rank recalculated 1-100 from refreshed market caps.')

    meta=payload.setdefault('meta',{})
    meta['version']='v8-live-market'
    meta['companiesResearched']=len(researched_set)
    meta['marketDataUpdated']=now.strftime('%Y-%m-%d %H:%M')
    meta['generatedAt']=now.isoformat(timespec='seconds')
    meta['universeValidation']=uv
    meta['rankPolicy']=(
        'Rank recalculated from market cap only after a successful Update All of all 100 constituents.'
        if len(researched_set)==100 else
        'Snapshot rank preserved until full 100-name coverage is available.'
    )
    meta['rankUpdatedAt']=now.isoformat(timespec='seconds') if rank_recalculated else meta.get('rankUpdatedAt')
    meta['automaticUpdatePolicy']={
        'autoFields':['price','marketCap','marketDataUpdated','marketDataProvider','universeValidation'],
        'conditionalAutoFields':['rank (Update All only, 100/100 quotes, zero failures)'],
        'protectedResearchFields':['valuation','score','framework','thesis','bear','moatStatus','moatReason','marketBelieves','marketMissing','variables','fit','teamComment'],
        'note':'Automatic updater never rewrites investment research intelligence.'
    }
    payload['stocks']=stocks
    DATA_FILE.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    status={
        'generatedAt':now.isoformat(timespec='seconds'),'target':target or 'ALL',
        'updatedStocks':updated,'failures':failures,'rankRecalculated':rank_recalculated,
        'universeValidation':uv,'logs':logs[-120:]
    }
    STATUS_FILE.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

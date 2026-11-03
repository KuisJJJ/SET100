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
UA = 'Mozilla/5.0 (compatible; SET100ResearchUpdater/1.0)'

def get_json(url, timeout=20):
    req=Request(url, headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*'})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def get_text(url, timeout=20):
    req=Request(url, headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml'})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8','ignore')

def yahoo_latest(ticker):
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
    return {'price':float(px),'asof':dt.isoformat(timespec='seconds'),'provider':'Yahoo Finance (.BK) fallback'}

def parse_set100_from_html():
    html=get_text(SET100_PAGE)
    candidates=re.findall(r'(?:>|&quot;|")([A-Z][A-Z0-9&.-]{1,11})(?:<|&quot;|")', html)
    stop={'SET','SET50','SET100','SET50FF','SET100FF','HTML','HEAD','BODY','HTTP','HTTPS','OPEN','HIGH','LOW','LAST','CHANGE','OFFER','VALUE','VOLUME'}
    out=[]
    for c in candidates:
        c=re.sub(r'[^A-Z0-9&.-]','',c.upper())
        if c and c not in stop and c not in out: out.append(c)
    return out if 80 <= len(out) <= 120 else []

def duplicates(stocks):
    seen=set(); dup=[]
    for s in stocks:
        t=s.get('ticker')
        if t in seen and t not in dup: dup.append(t)
        seen.add(t)
    return dup

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--ticker',default=''); args=ap.parse_args()
    payload=json.loads(DATA_FILE.read_text(encoding='utf-8'))
    stocks=payload.get('stocks',[]); target=args.ticker.strip().upper(); now=datetime.now(BKK)
    updated=0; failures=[]; logs=[]
    for s in stocks:
        if target and s.get('ticker')!=target: continue
        t=s.get('ticker','').upper(); old_px=s.get('price'); old_mc=s.get('marketCap')
        try:
            q=yahoo_latest(t)
            if not q: raise RuntimeError('no quote')
            shares=(float(old_mc)/float(old_px)) if old_px and old_mc and float(old_px)>0 else None
            s['price']=round(q['price'],4)
            if shares: s['marketCap']=round(shares*q['price'],2)
            s['marketDataUpdated']=q['asof'][:10]; s['marketDataProvider']=q['provider']
            updated+=1; logs.append(f"{t}: {old_px} -> {s['price']}")
            time.sleep(0.05)
        except Exception as e:
            failures.append({'ticker':t,'error':str(e)})
    if not target:
        rankable=[s for s in stocks if isinstance(s.get('marketCap'),(int,float))]
        rankable.sort(key=lambda s:s['marketCap'], reverse=True)
        for i,s in enumerate(rankable,1): s['rank']=i
        stocks.sort(key=lambda s:(s.get('rank',9999),s.get('ticker','')))
    official=[]; universe_error=None
    try:
        official=parse_set100_from_html()
        if not official: universe_error='Official SET100 HTML could not be parsed reliably; universe was NOT overwritten.'
    except Exception as e:
        universe_error=f'Official SET100 check failed: {e}'
    master=[s.get('ticker','').upper() for s in stocks if s.get('ticker')]; dup=duplicates(stocks)
    if official:
        off=set(official); mst=set(master)
        uv={'ok':not(off-mst or mst-off or dup),'checkedAt':now.isoformat(timespec='seconds'),'officialCount':len(off),'masterCount':len(mst),'missingInMaster':sorted(off-mst),'extraInMaster':sorted(mst-off),'duplicates':dup,'source':SET100_PAGE}
    else:
        uv={'ok':False,'checkedAt':now.isoformat(timespec='seconds'),'officialCount':None,'masterCount':len(set(master)),'missingInMaster':[],'extraInMaster':[],'duplicates':dup,'source':SET100_PAGE,'error':universe_error}
    meta=payload.setdefault('meta',{})
    meta['version']='v7-live-update'; meta['companiesResearched']=len(stocks); meta['marketDataUpdated']=now.strftime('%Y-%m-%d %H:%M'); meta['generatedAt']=now.isoformat(timespec='seconds'); meta['universeValidation']=uv
    meta['automaticUpdatePolicy']={'autoFields':['price','marketCap','rank','marketDataUpdated','universeValidation'],'protectedResearchFields':['valuation','score','framework','thesis','bear','moatStatus','moatReason','marketBelieves','marketMissing','variables','fit','teamComment'],'note':'Research Intelligence is never rewritten by the automatic updater.'}
    payload['stocks']=stocks
    DATA_FILE.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    status={'generatedAt':now.isoformat(timespec='seconds'),'target':target or 'ALL','updatedStocks':updated,'failures':failures,'universeValidation':uv,'logs':logs[-100:]}
    STATUS_FILE.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False,indent=2))

if __name__=='__main__': main()

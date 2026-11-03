#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'data.json'
BKK = timezone(timedelta(hours=7))
UA = 'Mozilla/5.0 (compatible; SET100ResearchUpdater/1.2)'
SET_SOURCE = 'https://www.set.or.th/en/market/index/set/overview'


def get_json(url, timeout=20):
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/json,text/plain,*/*'})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def yahoo_set_latest():
    # Secondary fallback quote feed. The official SET page remains the displayed source reference.
    symbol = quote('^SET.BK', safe='')
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d'
    j = get_json(url)
    res = (j.get('chart') or {}).get('result') or []
    if not res:
        raise RuntimeError('SET Index quote unavailable')
    r = res[0]
    meta = r.get('meta') or {}
    px = meta.get('regularMarketPrice')
    prior = meta.get('chartPreviousClose') or meta.get('previousClose')
    ts = meta.get('regularMarketTime')
    if px is None:
        closes = (((r.get('indicators') or {}).get('quote') or [{}])[0].get('close') or [])
        closes = [x for x in closes if x is not None]
        px = closes[-1] if closes else None
        prior = closes[-2] if len(closes) >= 2 else prior
    if px is None:
        raise RuntimeError('SET Index latest value missing')
    dt = datetime.fromtimestamp(ts, timezone.utc).astimezone(BKK) if ts else datetime.now(BKK)
    change = (float(px) - float(prior)) if prior not in (None, 0) else None
    change_pct = (change / float(prior) * 100) if change is not None and float(prior) else None
    return {
        'last': round(float(px), 2),
        'change': round(change, 2) if change is not None else None,
        'changePct': round(change_pct, 2) if change_pct is not None else None,
        'updatedAt': dt.isoformat(timespec='seconds'),
        'provider': 'Yahoo Finance ^SET.BK secondary fallback',
        'source': SET_SOURCE,
    }


def upsert_history(index, quote):
    history = index.setdefault('history', [])
    date = quote['updatedAt'][:10]
    # Preserve historical month-end observations. Replace only current/intraday point for the same date.
    history[:] = [p for p in history if not (str(p.get('date')) == date and p.get('type') in ('current', 'intraday'))]
    history.append({'date': date, 'value': quote['last'], 'type': 'current'})
    history.sort(key=lambda x: str(x.get('date', '')))
    window = index.setdefault('historyWindow', {})
    if history:
        window['start'] = history[0].get('date')
        window['end'] = history[-1].get('date')
        window['points'] = len(history)
    window['frequency'] = window.get('frequency') or 'monthly + current'
    window['defaultRange'] = window.get('defaultRange') or '3M'


def main():
    payload = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    q = yahoo_set_latest()
    idx = payload.setdefault('marketIndex', {})
    idx.update({
        'symbol': 'SET',
        'name': 'SET Index',
        'last': q['last'],
        'change': q['change'],
        'changePct': q['changePct'],
        'updatedAt': q['updatedAt'],
        'source': q['source'],
        'provider': q['provider'],
    })
    upsert_history(idx, q)
    payload.setdefault('meta', {})['setIndexUpdated'] = q['updatedAt']
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'SET': q}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

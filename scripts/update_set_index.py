#!/usr/bin/env python3
from __future__ import annotations
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'data.json'
BKK = timezone(timedelta(hours=7))
UA = 'Mozilla/5.0 (compatible; SET100ResearchUpdater/1.3)'
SET_SOURCE = 'https://www.set.or.th/en/market/index/set/overview'


def get_json(url, timeout=20):
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/json,text/plain,*/*'})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def last_non_null(values):
    if not values:
        return None
    for v in reversed(values):
        if v is not None:
            return v
    return None


def yahoo_set_latest():
    """Secondary fallback feed; official SET URL remains the displayed reference."""
    symbol = quote('^SET.BK', safe='')
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d'
    j = get_json(url)
    res = (j.get('chart') or {}).get('result') or []
    if not res:
        raise RuntimeError('SET Index quote unavailable')
    r = res[0]
    meta = r.get('meta') or {}
    quote_block = (((r.get('indicators') or {}).get('quote') or [{}])[0])
    closes = quote_block.get('close') or []
    px = meta.get('regularMarketPrice')
    if px is None:
        px = last_non_null(closes)
    if px is None:
        raise RuntimeError('SET Index latest value missing')

    prior = meta.get('chartPreviousClose') or meta.get('previousClose')
    if prior in (None, 0):
        non_null_closes=[x for x in closes if x is not None]
        prior=non_null_closes[-2] if len(non_null_closes)>=2 else None
    ts = meta.get('regularMarketTime')
    dt = datetime.fromtimestamp(ts, timezone.utc).astimezone(BKK) if ts else datetime.now(BKK)
    change = (float(px) - float(prior)) if prior not in (None, 0) else None
    change_pct = (change / float(prior) * 100) if change is not None and float(prior) else None

    # Use only fields actually delivered by this feed. Never retain stale OHLC/value.
    day_open = meta.get('regularMarketOpen')
    day_high = meta.get('regularMarketDayHigh')
    day_low = meta.get('regularMarketDayLow')
    volume = meta.get('regularMarketVolume')
    if day_open is None: day_open = last_non_null(quote_block.get('open') or [])
    if day_high is None: day_high = last_non_null(quote_block.get('high') or [])
    if day_low is None: day_low = last_non_null(quote_block.get('low') or [])
    if volume is None: volume = last_non_null(quote_block.get('volume') or [])

    return {
        'last': round(float(px), 2),
        'change': round(change, 2) if change is not None else None,
        'changePct': round(change_pct, 2) if change_pct is not None else None,
        'open': round(float(day_open), 2) if day_open is not None else None,
        'high': round(float(day_high), 2) if day_high is not None else None,
        'low': round(float(day_low), 2) if day_low is not None else None,
        'volumeThousandShares': round(float(volume)/1000, 0) if volume is not None else None,
        'valueMillionBaht': None,
        'status': 'Secondary delayed feed',
        'updatedAt': dt.isoformat(timespec='seconds'),
        'provider': 'Yahoo Finance ^SET.BK secondary fallback',
        'source': SET_SOURCE,
        'dataQualityNote': 'SET official page is the reference. Secondary feed supplies live/delayed quote; fields not supplied are explicitly null rather than carried forward from an old date.'
    }


def official_set_turnover():
    """Official SET Marketplace delayed quotation. Requires subscribed API key.

    The documented Index Quotation API exposes cumulative totalValue.
    The API's numeric scale is not assumed: caller must explicitly configure
    SET_INDEX_VALUE_UNIT as 'baht', 'thousand_baht', or 'million_baht'.
    """
    key = os.environ.get('SET_MARKETPLACE_API_KEY', '').strip()
    if not key:
        return None, 'SET Marketplace API key ยังไม่ได้ตั้งค่า'
    unit = os.environ.get('SET_INDEX_VALUE_UNIT', '').strip().lower()
    multipliers = {'baht': 1/1_000_000, 'thousand_baht': 1/1000, 'million_baht': 1}
    if unit not in multipliers:
        return None, 'ยังไม่ได้ยืนยันหน่วยของ SET Marketplace (SET_INDEX_VALUE_UNIT)'
    url = 'https://marketplace.set.or.th/api/public/delay-data/index?indexSector=SET'
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/json', 'api-key': key})
    try:
        with urlopen(req, timeout=20) as response:
            raw = json.loads(response.read().decode('utf-8'))
        items = raw if isinstance(raw, list) else raw.get('data', raw.get('indices', raw.get('result', [])))
        if isinstance(items, dict):
            items = items.get('items', items.get('indices', [items]))
        if not isinstance(items, list):
            raise ValueError('Unsupported SET Marketplace response structure')
        match = next((x for x in items if isinstance(x, dict) and str(x.get('symbol', '')).upper() == 'SET'), None)
        if not match:
            raise ValueError('SET index record missing from official response')
        value = match.get('totalValue')
        if value is None:
            raise ValueError('totalValue is missing')
        raw_date = match.get('time')
        if not raw_date:
            raise ValueError('Trading timestamp is missing')
        timestamp = datetime.fromisoformat(str(raw_date).replace('Z', '+00:00')).astimezone(BKK)
        return {'valueMillionBaht': round(float(value) * multipliers[unit], 2),
                'valueUpdatedAt': timestamp.isoformat(timespec='seconds'),
                'valueProvider': 'SET Marketplace delayed index quotation'}, None
    except Exception as exc:
        return None, f'ไม่สามารถดึงมูลค่าซื้อขายจาก SET: {type(exc).__name__}'



def yahoo_set_daily_history():
    """Fetch up to five years of genuine SET daily close prices, not sparse monthly samples.

    Yahoo's index daily *volume* is not SET's traded-value-in-THB field.
    Historical traded value is deliberately null until licensed SET EOD data
    is connected.
    """
    symbol = quote('^SET.BK', safe='')
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5y&interval=1d'
    j = get_json(url, timeout=30)
    results = (j.get('chart') or {}).get('result') or []
    if not results:
        raise RuntimeError('Daily SET history unavailable')
    r = results[0]
    timestamps = r.get('timestamp') or []
    q = (((r.get('indicators') or {}).get('quote') or [{}])[0])
    closes = q.get('close') or []
    by_day = {}
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        try:
            value = float(close)
            if not (value > 0):
                continue
            date = datetime.fromtimestamp(int(ts), timezone.utc).astimezone(BKK).date().isoformat()
            by_day[date] = {'date': date, 'value': round(value, 2),
                            'valueMillionBaht': None, 'type': 'daily',
                            'priceProvider': 'Yahoo Finance ^SET.BK delayed'}
        except (ValueError, TypeError, OverflowError):
            continue
    if not by_day:
        raise RuntimeError('Daily SET history contained no valid closes')
    return [by_day[k] for k in sorted(by_day)]

def upsert_history(index, quote):
    history = index.setdefault('history', [])
    date = quote['updatedAt'][:10]
    history[:] = [p for p in history if not (str(p.get('date')) == date and p.get('type') in ('current', 'intraday'))]
    history.append({'date': date, 'value': quote['last'], 'type': 'current'})
    history.sort(key=lambda x: str(x.get('date', '')))
    window = index.setdefault('historyWindow', {})
    if history:
        window['start'] = history[0].get('date')
        window['end'] = history[-1].get('date')
        window['points'] = len(history)
    window['frequency'] = 'monthly + current'
    window['defaultRange'] = window.get('defaultRange') or '3M'


def main():
    payload = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    q = yahoo_set_latest()
    official, official_error = official_set_turnover()
    if official:
        # Only show turnover when the official quote refers to the same trading date.
        if official['valueUpdatedAt'][:10] == q['updatedAt'][:10]:
            q.update(official)
        else:
            official_error = 'วันที่มูลค่าซื้อขาย SET ไม่ตรงกับวันที่ดัชนีจากแหล่งรอง'
    if not official or official_error:
        q['valueMillionBaht'] = None
        q['valueUpdatedAt'] = None
        q['valueProvider'] = None
    q['valueDataStatus'] = 'พร้อมแสดง' if q['valueMillionBaht'] is not None else (official_error or 'ไม่มีข้อมูล')
    idx = payload.setdefault('marketIndex', {})
    idx.update({
        'symbol': 'SET','name': 'SET Index','last': q['last'],
        'change': q['change'],'changePct': q['changePct'],
        'open': q['open'],'high': q['high'],'low': q['low'],
        'volumeThousandShares': q['volumeThousandShares'],
        'valueMillionBaht': q['valueMillionBaht'],
        'valueUpdatedAt': q.get('valueUpdatedAt'),
        'valueProvider': q.get('valueProvider'),
        'valueDataStatus': q['valueDataStatus'],
        'status': q['status'],'updatedAt': q['updatedAt'],
        'source': q['source'],'provider': q['provider'],
        'dataQualityNote': q['dataQualityNote'],
    })
    upsert_history(idx, q)
    try:
        daily = yahoo_set_daily_history()
        day = q['updatedAt'][:10]
        # Keep intraday quote separate from the EOD closing-price series.
        # Any official trading value must match its quote date exactly.
        if q.get('valueMillionBaht') is not None:
            for row in daily:
                if row['date'] == day:
                    row['valueMillionBaht'] = q['valueMillionBaht']
                    row['valueProvider'] = q.get('valueProvider')
                    row['turnoverIsIntraday'] = True
        idx['dailyHistory'] = daily
        idx['dailyHistoryProvider'] = 'Yahoo Finance ^SET.BK (ราคาดัชนีรายวัน); SET Marketplace (มูลค่าซื้อขายเฉพาะวันที่มีข้อมูลที่ตรวจสอบแล้ว)'
        idx['dailyHistoryUpdatedAt'] = datetime.now(BKK).isoformat(timespec='seconds')
        idx['dailyHistoryStatus'] = 'ok'
    except Exception as exc:
        # Do not remove previously verified history during temporary outage.
        idx['dailyHistoryStatus'] = f'unavailable: {type(exc).__name__}'
    payload.setdefault('meta', {})['setIndexUpdated'] = q['updatedAt']
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'SET': q}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

"""Read Settrade's public SSR snapshot without executing downloaded JavaScript.

Amounts in financial charts are THB thousands; dashboard uses THB millions.
Quote marketCap is THB. Dates always come from the source, never fetch time.
"""
import json
import re
from urllib.request import Request, urlopen


class LiteralReader:
    def __init__(self, source, bindings=None):
        self.s, self.i, self.bindings = source, 0, bindings or {}

    def space(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def take(self, expected):
        self.space()
        if not self.s.startswith(expected, self.i):
            raise ValueError(f'Invalid snapshot syntax at {self.i}')
        self.i += len(expected)

    def value(self):
        self.space()
        ch = self.s[self.i]
        if self.s.startswith('void 0', self.i):
            self.i += 6
            return None
        if ch == '"':
            v, n = json.JSONDecoder().raw_decode(self.s[self.i:])
            self.i += n
            return v
        if ch in '[{':
            self.i += 1
            end = ']' if ch == '[' else '}'
            out = [] if ch == '[' else {}
            self.space()
            while self.s[self.i] != end:
                if ch == '[':
                    out.append(self.value())
                else:
                    self.space()
                    if self.s[self.i] == '"':
                        key = self.value()
                    else:
                        m = re.match(r'[\w$]+', self.s[self.i:])
                        if not m:
                            raise ValueError('Invalid snapshot key')
                        key = m[0]
                        self.i += len(key)
                    self.take(':')
                    out[key] = self.value()
                self.space()
                if self.s[self.i] == end:
                    break
                self.take(',')
                self.space()
            self.take(end)
            return out
        if self.s.startswith('new Date(', self.i):
            self.take('new Date(')
            value = self.value()
            self.take(')')
            return value
        m = re.match(r'-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', self.s[self.i:])
        if m:
            self.i += len(m[0])
            return float(m[0]) if any(c in m[0] for c in ".eE") else int(m[0])
        m = re.match(r'[\w$]+', self.s[self.i:])
        if not m:
            raise ValueError('Unsupported snapshot expression')
        self.i += len(m[0])
        if m[0] in ('null', 'true', 'false'):
            return json.loads(m[0])
        if m[0] not in self.bindings:
            raise ValueError('Unknown snapshot binding')
        return self.bindings[m[0]]


def decode_snapshot(html):
    m = re.search(r'<script>window\.__NUXT__=\(function\((.*?)\)\{return (.*?)\}\((.*?)\)\);?</script>', html, re.S)
    if not m:
        raise ValueError('Settrade snapshot not available')
    params = m[1].split(',')
    args = LiteralReader('[' + m[3] + ']').value()
    if len(params) != len(args):
        raise ValueError('Snapshot binding mismatch')
    return LiteralReader(m[2], dict(zip(params, args))).value()


def fetch_page(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'})
    with urlopen(req, timeout=35) as r:
        html = r.read(5_000_000).decode('utf-8')
    return decode_snapshot(html)


def fetch_news(ticker):
    page = fetch_page(f'https://www.settrade.com/th/equities/quote/{ticker}/news')
    for key, value in page['fetch'].items():
        if key.startswith('MiscEquityNews:'):
            return value.get('dataNewsSET', {}).get('items', [])
    raise ValueError('Official news list unavailable')


def fetch_f45(ticker, news_id):
    url = f'https://www.settrade.com/th/news-and-articles/news/{news_id}?symbol={ticker}'
    d = fetch_page(url)['state']['news-and-articles']['news']['newsDetail']
    if d.get('symbol') != ticker or 'F45' not in d.get('headline', ''):
        raise ValueError('F45 source identity mismatch')
    d['sourceUrl'] = url
    return {k: d.get(k) for k in ('symbol', 'headline', 'datetime', 'downloadUrl', 'content', 'sourceUrl')}


def fetch_stock(ticker):
    if not re.fullmatch(r'[A-Z0-9&.-]+', ticker):
        raise ValueError('Invalid ticker')
    url = f'https://www.settrade.com/th/equities/quote/{ticker}/financial-statement/five-years'
    stock = fetch_page(url)['state']['equity']['stock']
    if stock.get('info', {}).get('symbol') != ticker:
        raise ValueError('Source returned another ticker')
    return {'sourceUrl': url, 'quote': stock['info'],
            'financial': stock['common']['financialStatement']}

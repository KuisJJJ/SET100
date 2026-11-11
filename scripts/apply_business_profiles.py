#!/usr/bin/env python3
"""Project curated, source-linked business introductions into dashboard data.

These are qualitative business-model descriptions, not quarterly segment data.
Market/financial refreshes must never fabricate or rewrite this editorial layer.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_profiles(root=ROOT):
    content = json.loads((root/'business_profiles.json').read_text(encoding='utf-8'))
    profiles = content['profiles']
    if content['coverage'] != len(profiles):
        raise ValueError('Business profile coverage mismatch')
    for ticker, profile in profiles.items():
        for key in ('companyName','overview','customers','revenueDrivers','basisNote','checkedOn'):
            if not isinstance(profile.get(key), str) or not profile[key].strip():
                raise ValueError(f'{ticker}: missing {key}')
        if profile.get('informationBasis') != 'qualitative_business_model':
            raise ValueError(f'{ticker}: unsupported revenue evidence basis')
        if not profile.get('revenueStreams') or not all(s.get('label') and s.get('description') for s in profile['revenueStreams']):
            raise ValueError(f'{ticker}: missing revenue channels')
        if not profile.get('sources') or not all(s.get('url','').startswith('https://') for s in profile['sources']):
            raise ValueError(f'{ticker}: missing sources')
    return profiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    data_path = ROOT/'data.json'
    data = json.loads(data_path.read_text(encoding='utf-8'))
    profiles = load_profiles()
    missing = [s['ticker'] for s in data['stocks'] if s['ticker'] not in profiles]
    if missing:
        raise ValueError('Missing business profiles: '+', '.join(missing))
    for stock in data['stocks']:
        profile = profiles[stock['ticker']]
        if args.check:
            if stock.get('businessProfile') != profile:
                raise ValueError(f"{stock['ticker']}: published profile differs from curated source")
        else:
            stock['businessProfile'] = profile
    if not args.check:
        data['meta']['businessProfilesCheckedOn'] = max(p['checkedOn'] for p in profiles.values())
        data['meta']['businessProfilesCoverage'] = len(data['stocks'])
        data_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Business introductions {'checked' if args.check else 'applied'}: {len(data['stocks'])}")


if __name__=='__main__':main()

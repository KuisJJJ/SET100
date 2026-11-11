import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from apply_business_profiles import load_profiles


class BusinessProfiles(unittest.TestCase):
    def test_complete_source_linked_business_and_revenue_explanations(self):
        profiles = load_profiles()
        data = json.loads((ROOT/'data.json').read_text())
        self.assertEqual(set(profiles), {s['ticker'] for s in data['stocks']})
        for stock in data['stocks']:
            t = stock['ticker']
            with self.subTest(ticker=t):
                p = profiles[t]
                self.assertEqual(stock['businessProfile'], p)
                self.assertEqual(p['informationBasis'], 'qualitative_business_model')
                self.assertIsNone(p['sourcePeriod'])
                self.assertTrue(p['basisNote'])
                self.assertIn('/quote/'+t+'/company-profile',p['sources'][0]['url'])
                self.assertTrue(all('percentage' not in row for row in p['revenueStreams']))

    def test_excel_rebuild_preserves_business_and_verified_financials(self):
        before = {s['ticker']:s for s in json.loads((ROOT/'data.json').read_text())['stocks']}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'scripts').mkdir()
            for name in ('excel_to_json.py','apply_business_profiles.py'):
                shutil.copy(ROOT/'scripts'/name,root/'scripts'/name)
            for name in ('data.json','business_profiles.json','financial_snapshots.json','SET100_Investment_Research_Master.xlsx'):
                shutil.copy(ROOT/name,root/name)
            subprocess.run([sys.executable,str(root/'scripts/excel_to_json.py')],check=True,capture_output=True)
            after = json.loads((root/'data.json').read_text())['stocks']
            self.assertEqual(len(after),len(before))
            for stock in after:
                with self.subTest(ticker=stock['ticker']):
                    original = before[stock['ticker']]
                    for key in ('businessProfile','qNpat','periodNpat','financialPeriodEnd','marketDataAsOf'):
                        self.assertEqual(stock[key],original[key])
                    self.assertNotIn('score',stock)


if __name__=='__main__':unittest.main()

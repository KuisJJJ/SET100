import copy
from datetime import date
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from settrade_source import decode_snapshot
from update_financial_data import parse_f45, growth, research_end, target_period_end, structured_facts, apply_snapshot


class FinancialUpdates(unittest.TestCase):
    def test_literal_decoder_does_not_execute_code(self):
        html = '<script>window.__NUXT__=(function(a,b){return {x:a,y:b}}(null,.25));</script>'
        self.assertEqual(decode_snapshot(html), {'x':None,'y':.25})
        with self.assertRaises(ValueError):
            decode_snapshot(html.replace('.25', 'fetch("https://example.com")'))

    def test_negative_and_zero_growth_bases(self):
        self.assertIsNone(growth(100,-50))
        self.assertIsNone(growth(100,0))
        self.assertEqual(growth(-50,100),-150)

    def test_fiscal_reporting_dates(self):
        self.assertEqual(research_end({'ticker':'AOT','period':'9M FY2026 / Q3 FY2026'}),'2026-06-30')
        self.assertEqual(research_end({'ticker':'AEONTS','period':'6M FY2027 / Q2 FY2027'}),'2026-08-31')
        self.assertEqual(target_period_end(date(2027,1,5)),'2026-12-31')

    def test_f45_units_and_loss(self):
        d={'headline':'ไตรมาสที่ 3 (F45) (ก่อนสอบทาน)', 'datetime':'2026-10-21T17:04:00+07:00',
           'sourceUrl':'https://www.settrade.com/example',
           'content':'(หน่วย : พันบาท)\nสิ้นสุดวันที่ 30 กันยายน\nปี 2569 2568 2569 2568\nกำไร (ขาดทุน) 1,200 (500) 3,000 2,000\n*สำหรับงบการเงินรวม'}
        f=parse_f45(d,date(2026,11,10))
        self.assertEqual((f['qNpat'],f['quarterPriorNpat'],f['periodNpat']),(1.2,-.5,3))
        self.assertEqual(f['financialPeriodEnd'],'2026-09-30')
        self.assertEqual(f['financialAssurance'],'ก่อนสอบทาน')
        with self.assertRaises(ValueError):parse_f45(d,date(2026,10,1))
        d['content']=d['content'].replace('พันบาท','USD')
        with self.assertRaises(ValueError):parse_f45(d,date(2026,11,10))

    def test_newest_filing_wins_regardless_of_news_order(self):
        row={'symbol':'TEST','fsType':'C','quarter':'6M','year':2026,
             'beginDate':'2026-01-01','endDate':'2026-06-30','netProfit':1000}
        snapshot={'sourceUrl':'https://www.settrade.com/test','quote':{},'financial':{
            'financialDataAccumulatedChart':[row], 'financialDataQuarterChart':[dict(row,quarter='Q2')]}}
        filing={'headline':'ไตรมาสที่ 3 (F45) (สอบทานแล้ว)', 'datetime':'2026-11-01T12:00:00+07:00',
                'sourceUrl':'https://www.settrade.com/old','content':
                '(หน่วย : พันบาท)\nสิ้นสุดวันที่ 30 กันยายน\nปี 2569 2568 2569 2568\nกำไร (ขาดทุน) 1,000 500 3,000 2,000\n*สำหรับงบการเงินรวม'}
        revision=dict(filing,datetime='2026-11-02T12:00:00+07:00',sourceUrl='https://www.settrade.com/revision',
                      content=filing['content'].replace('3,000','4,000'))
        for news in ([filing,revision],[revision,filing]):
            stock={'ticker':'TEST','period':'1H2026 / Q2 2026','researchReviewed':'2026-10-01'}
            apply_snapshot(stock,snapshot,{'f45':news},'2026-11-10T17:00:00+07:00')
            self.assertEqual(stock['periodNpat'],4)
            self.assertEqual(stock['financialSourceUrl'],revision['sourceUrl'])
            self.assertEqual(stock['financialPeriodEnd'],'2026-09-30')

    def test_financial_and_price_provenance_for_all_companies(self):
        data=json.loads((ROOT/'data.json').read_text())
        self.assertEqual(len({s['ticker'] for s in data['stocks']}),100)
        for s in data['stocks']:
            with self.subTest(ticker=s['ticker']):
                self.assertTrue(s.get('financialPeriodEnd'))
                self.assertTrue(s.get('financialSourceUrl','').startswith('https://www.settrade.com/'))
                self.assertTrue(s.get('marketDataAsOf'))
                self.assertTrue(s.get('researchFinancialPeriod'))
                self.assertNotEqual(s['updateStatus'],'Current')
                self.assertAlmostEqual(s['npatGrowth'],growth(s['periodNpat'],s.get('priorPeriodNpat'))) if s['npatGrowth'] is not None else None


if __name__=='__main__':unittest.main()

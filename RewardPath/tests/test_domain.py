import copy
import json
import tempfile
import unittest
from pathlib import Path
from domain import Store, CATALOG, evaluate, compare, cents

PROFILE={'age':30,'country':'US','max_upfront_cents':0,'remote_only':True,'use_ai':True,'allow_human_writing':False}
NOW='2026-10-19T22:00:00Z'
class DomainTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'test.sqlite3')
    def tearDown(self):self.tmp.cleanup()
    def plan(self):return self.store.create(['demo-review'],PROFILE,NOW)
    def submitted(self):
        p=self.plan();self.store.update(p['id'],'demo-review:prepare');return self.store.update(p['id'],'demo-review:submit','Synthetic submission receipt 1')
    def awarded(self):
        p=self.submitted();return self.store.award(p['id'],'demo-review',3000,'USD','Synthetic award notice','demo:award-1')
    def test_pass_and_unknown(self):
        self.assertEqual(evaluate('demo-review',PROFILE,NOW)['status'],'pass')
        self.assertEqual(evaluate('demo-review',{**PROFILE,'age':None},NOW)['status'],'unknown')
        self.assertEqual(evaluate('demo-unclear',PROFILE,NOW)['status'],'unknown')
        self.assertEqual(evaluate('amazon-alexa',PROFILE,NOW)['status'],'unknown')
    def test_no_spend(self):self.assertEqual(evaluate('demo-spend',PROFILE,NOW)['status'],'fail')
    def test_conflicts(self):self.assertFalse(compare(['demo-bounty','demo-design'],PROFILE,NOW)['can_create_plan'])
    def test_missing_prerequisite(self):
        old=CATALOG[0]['prerequisites'];CATALOG[0]['prerequisites']=['missing']
        try:self.assertFalse(compare(['demo-review'],PROFILE,NOW)['can_create_plan'])
        finally:CATALOG[0]['prerequisites']=old
    def test_timezone_deadline(self):
        self.assertEqual(evaluate('demo-review',PROFILE,'2026-11-05T16:59:59-04:00')['status'],'pass')
        self.assertEqual(evaluate('demo-review',PROFILE,'2026-11-05T17:00:00-04:00')['status'],'fail')
        with self.assertRaises(ValueError):evaluate('demo-review',PROFILE,'2026-10-19T22:00:00')
    def test_money_types(self):
        for bad in [True,False,1.5,'30',-1,0]:
            with self.assertRaises(ValueError):cents(bad)
        self.assertEqual(cents(1),1)
    def test_exact_cents_and_unverified(self):
        p=self.awarded();p=self.store.receipt(p['id'],p['awards'][0]['id'],2999,'USD',NOW,'Synthetic payment fixture','demo:receipt-1')
        self.store.receipt(p['id'],p['awards'][0]['id'],1,'USD',NOW,'Synthetic final cent','demo:receipt-2')
        self.assertEqual(self.store.ledger()['synthetic_receipts_cents'],3000)
        self.assertEqual(self.store.ledger()['verified_received_cents'],0)
    def test_duplicate_and_immutable_error(self):
        p=self.awarded();p=self.store.receipt(p['id'],p['awards'][0]['id'],1000,'USD',NOW,'Synthetic','demo:Receipt-X')
        before=self.store.all()
        with self.assertRaises(ValueError):self.store.receipt(p['id'],p['awards'][0]['id'],1000,'USD',NOW,'Synthetic',' DEMO:receipt-x ')
        self.assertEqual(before,self.store.all())
    def test_invalid_transitions(self):
        p=self.plan()
        with self.assertRaises(ValueError):self.store.update(p['id'],'demo-review:submit','Fake order')
        with self.assertRaises(ValueError):self.store.award(p['id'],'demo-review',3000,'USD','Notice','demo:award')
        with self.assertRaises(ValueError):self.store.receipt(p['id'],'missing',3000,'USD',NOW,'Receipt','demo:receipt')
    def test_no_blank_evidence(self):
        p=self.plan();self.store.update(p['id'],'demo-review:prepare')
        with self.assertRaises(ValueError):self.store.update(p['id'],'demo-review:submit','  ')
    def test_currency_overpayment_future(self):
        p=self.awarded();aid=p['awards'][0]['id']
        for amount,currency,date in [(1,'EUR',NOW),(3001,'USD',NOW),(1,'USD','2099-01-01T00:00:00Z')]:
            with self.assertRaises(ValueError):self.store.receipt(p['id'],aid,amount,currency,date,'Synthetic','demo:x')
    def test_persistence(self):
        p=self.plan();self.assertEqual(Store(self.store.path).all()[0]['id'],p['id'])
    def test_unknown_cannot_create(self):
        with self.assertRaises(ValueError):self.store.create(['demo-unclear'],PROFILE,NOW)
    def test_distinct_and_bounds(self):
        with self.assertRaises(ValueError):compare(['demo-review','demo-review'],PROFILE,NOW)
        with self.assertRaises(ValueError):evaluate('demo-review',{**PROFILE,'max_upfront_cents':True},NOW)
    def test_synthetic_mixing(self):
        with self.assertRaises(ValueError):self.store.create(['demo-review','amazon-alexa'],{**PROFILE,'affiliations_clear':True,'ownership_confirmed':True},NOW)
if __name__=='__main__':unittest.main()

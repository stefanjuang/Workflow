"""Evidence-first opportunity planning. All amounts are integer cents."""
import copy
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
CATALOG = json.loads((ROOT / 'catalog.json').read_text())


def timestamp(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value, str):
        raise ValueError('Date must be an ISO-8601 string with a timezone.')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Date must be valid ISO-8601.')
    if result.tzinfo is None:
        raise ValueError('A timezone is required.')
    return result.astimezone(timezone.utc)


def cents(value, label='Amount', allow_zero=False):
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise ValueError(f'{label} must be integer cents {"at least zero" if allow_zero else "greater than zero"}.')
    if value > 100_000_000:
        raise ValueError(f'{label} exceeds the prototype limit.')
    return value


def evidence(value, label='Evidence'):
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise ValueError(f'{label} must contain 1–2000 characters.')
    return value.strip()


def opportunity(oid):
    for row in CATALOG:
        if row['id'] == oid:
            return copy.deepcopy(row)
    raise ValueError('Unknown opportunity ID.')


def evaluate(oid, profile, now=None):
    row = opportunity(oid)
    if not isinstance(profile, dict):
        raise ValueError('Profile must be an object.')
    checks = []
    def add(key, state, reason):
        checks.append({'key': key, 'status': state, 'reason': reason})
    age = profile.get('age')
    if age is None:
        add('age','unknown','Age has not been supplied.')
    elif type(age) is not int or age < 0 or age > 120:
        raise ValueError('Age must be an integer from 0 to 120.')
    else:
        add('age','pass' if age >= row['min_age'] else 'fail',f"Minimum age: {row['min_age']}.")
    if not row.get('synthetic', False):
        majority = profile.get('legal_majority_confirmed')
        if majority is not None and type(majority) is not bool:
            raise ValueError('legal_majority_confirmed must be boolean or null.')
        add('legal_majority', 'unknown' if majority is None else ('pass' if majority else 'fail'), 'Legal age of majority where you reside requires explicit confirmation.')
    country = profile.get('country')
    add('country', 'unknown' if not country else ('pass' if country in row['countries'] else 'fail'), 'Country must match the checked eligibility scope; this catalog only evaluates US participation.')
    limit = profile.get('max_upfront_cents')
    if limit is None:
        add('upfront','unknown','An upfront-spend limit has not been set.')
    else:
        cents(limit, 'Spend limit', True)
        add('upfront','pass' if row['upfront_cents'] <= limit else 'fail',f"Requires {row['upfront_cents']} cents upfront; limit is {limit} cents.")
    for key in ['remote_only','use_ai','allow_human_writing']:
        if key in profile and profile[key] is not None and type(profile[key]) is not bool:
            raise ValueError(f'{key} must be a boolean or null.')
    if profile.get('remote_only') is None:
        add('remote','unknown','Remote-only preference has not been set.')
    else:
        add('remote','fail' if profile['remote_only'] and not row['remote'] else 'pass','Remote work is supported.' if row['remote'] else 'In-person activity is required.')
    if profile.get('use_ai') is None:
        add('ai','unknown','AI-use preference has not been set.')
    elif not profile['use_ai']:
        add('ai','pass','AI assistance is not requested.')
    else:
        add('ai','unknown' if row['ai_allowed'] is None else ('pass' if row['ai_allowed'] else 'fail'),'AI-use permission is unspecified.' if row['ai_allowed'] is None else 'AI-use rule checked.')
    if row['human_writing_required'] and profile.get('allow_human_writing') is not True:
        add('human_work','unknown' if profile.get('allow_human_writing') is None else 'fail','Human-authored work is required.')
    else:
        add('human_work','pass','No special human-writing requirement is listed in this fixture.')
    add('deadline','pass' if timestamp(now) < timestamp(row['deadline']) else 'fail',f"Closes {row['deadline']}.")
    if row.get('requires_affiliation_check'):
        for key, label in [('affiliations_clear','Sponsor, judge and family conflicts'),('ownership_confirmed','Ownership and authority to publish')]:
            val=profile.get(key)
            if val is not None and type(val) is not bool:
                raise ValueError(f'{key} must be a boolean or null.')
            add(key, 'unknown' if val is None else ('pass' if val else 'fail'),f'{label} require an explicit check.')
    status = 'fail' if any(c['status']=='fail' for c in checks) else ('unknown' if any(c['status']=='unknown' for c in checks) else 'pass')
    return {'opportunity':row,'status':status,'checks':checks,'scope':'A bounded rule check, not an eligibility certification or legal advice.','checked_at':timestamp(now).isoformat()}


def compare(ids, profile, now=None):
    if not isinstance(ids,list) or not ids or len(ids)>10 or len(set(ids))!=len(ids):
        raise ValueError('Choose 1–10 distinct opportunity IDs.')
    evaluations=[evaluate(oid,profile,now) for oid in ids]
    conflicts=[]
    groups={}
    for ev in evaluations:
        r=ev['opportunity']
        for group in r['conflict_groups']:
            if group in groups:
                conflicts.append({'group':group,'opportunities':[groups[group],r['id']],'reason':'These sample terms prohibit stacking the same entry.'})
            groups[group]=r['id']
        for pre in r['prerequisites']:
            if pre not in ids:
                conflicts.append({'prerequisite':pre,'opportunities':[r['id']],'reason':'A required prerequisite is missing.'})
    totals={kind:0 for kind in ['guaranteed_after_conditions','competitive','discretionary']}
    for ev in evaluations:
        totals[ev['opportunity']['reward_kind']]+=ev['opportunity']['cash_cents']
    upfront=sum(e['opportunity']['upfront_cents'] for e in evaluations)
    limit=profile.get('max_upfront_cents')
    if limit is not None and upfront > limit:
        conflicts.append({'group':'total_upfront_budget','opportunities':ids,'reason':f'Combined upfront cost {upfront} cents exceeds total limit {limit} cents.'})
    eligible=all(e['status']=='pass' for e in evaluations) and not conflicts
    return {'evaluations':evaluations,'conflicts':conflicts,'can_create_plan':eligible,'headline_cents_by_kind':totals,'upfront_cents':sum(e['opportunity']['upfront_cents'] for e in evaluations),'currency':'USD','expected_value':None,'warning':'No win probabilities are known. Headline amounts are not expected earnings or money received.'}


class Store:
    def __init__(self, path=None):
        self.path=str(path or os.environ.get('REWARDPATH_DB',ROOT/'.data/rewardpath.sqlite3'))
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as con:
            con.execute('CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    def connect(self):
        return sqlite3.connect(self.path, timeout=10)
    def _read(self,con,pid):
        row=con.execute('SELECT body FROM plans WHERE id=?',(pid,)).fetchone()
        if not row: raise ValueError('Unknown plan ID.')
        return json.loads(row[0])
    def _write(self,con,plan):
        plan['updated_at']=timestamp().isoformat()
        con.execute('INSERT OR REPLACE INTO plans VALUES (?,?)',(plan['id'],json.dumps(plan)))
    def all(self):
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute('SELECT body FROM plans ORDER BY rowid DESC')]
    def create(self, ids,profile,now=None):
        result=compare(ids,profile,now)
        if not result['can_create_plan']:
            raise ValueError('Plan blocked: resolve failed/unknown eligibility checks, conflicts and prerequisites first.')
        rows=[e['opportunity'] for e in result['evaluations']]
        if len({r['synthetic'] for r in rows})>1:
            raise ValueError('Synthetic examples and real opportunities must use separate plans.')
        plan={'id':str(uuid.uuid4()),'created_at':timestamp().isoformat(),'synthetic':rows[0]['synthetic'],'opportunities':rows,'checks':result,'obligations':[], 'awards':[], 'receipts':[]}
        for r in rows:
            for i,ob in enumerate(r['obligations']):
                plan['obligations'].append({**ob,'id':f"{r['id']}:{ob['id']}",'opportunity_id':r['id'],'kind':ob['id'],'status':'pending','evidence':'','prerequisite':None if i==0 else f"{r['id']}:{r['obligations'][i-1]['id']}"})
        with self.connect() as con: self._write(con,plan)
        return plan
    def update(self,pid,obid,description=''):
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            p=self._read(con,pid)
            ob=next((o for o in p['obligations'] if o['id']==obid),None)
            if ob is None: raise ValueError('Unknown obligation ID.')
            if ob['status']=='complete': raise ValueError('Obligation is already complete.')
            if ob['prerequisite'] and not any(o['id']==ob['prerequisite'] and o['status']=='complete' for o in p['obligations']):
                raise ValueError('Complete the preceding obligation first.')
            if ob['evidence_required']: description=evidence(description,'Submission evidence')
            elif description: description=evidence(description)
            ob.update(status='complete',evidence=description,completed_at=timestamp().isoformat())
            self._write(con,p)
        return p
    def award(self,pid,oid,amount,currency,description,source_ref):
        cents(amount)
        description=evidence(description)
        source_ref=evidence(source_ref,'Source reference')
        if currency!='USD': raise ValueError('This prototype supports USD only; no currency conversions are inferred.')
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            p=self._read(con,pid)
            row=next((r for r in p['opportunities'] if r['id']==oid),None)
            if row is None: raise ValueError('Opportunity is not in this plan.')
            if not all(o['status']=='complete' for o in p['obligations'] if o['opportunity_id']==oid):
                raise ValueError('Submission evidence must be recorded before an award.')
            if any(a['opportunity_id']==oid for a in p['awards']): raise ValueError('An award is already recorded for this opportunity.')
            if amount>row['cash_cents']: raise ValueError('Award exceeds this catalog headline; recheck the source before recording.')
            if p['synthetic'] and not source_ref.startswith('demo:'): raise ValueError('Synthetic records require a demo: source reference.')
            if not p['synthetic'] and source_ref.startswith('demo:'): raise ValueError('Synthetic evidence cannot substantiate a real award.')
            a={'id':str(uuid.uuid4()),'opportunity_id':oid,'amount_cents':amount,'currency':currency,'evidence':description,'source_ref':source_ref,'verification_status':'unverified','synthetic':p['synthetic'],'recorded_at':timestamp().isoformat()}
            p['awards'].append(a)
            self._write(con,p)
        return p
    def receipt(self,pid,aid,amount,currency,received_at,description,source_ref):
        cents(amount)
        description=evidence(description)
        source_ref=evidence(source_ref,'Source reference')
        dt=timestamp(received_at)
        if dt>timestamp(): raise ValueError('A receipt date cannot be in the future.')
        if currency!='USD': raise ValueError('This prototype supports USD only.')
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            p=self._read(con,pid)
            award=next((a for a in p['awards'] if a['id']==aid),None)
            if not award: raise ValueError('A recorded award is required before a receipt.')
            allplans=[json.loads(r[0]) for r in con.execute('SELECT body FROM plans')]
            if any(r['source_ref'].casefold()==source_ref.casefold() for q in allplans for r in q['receipts']): raise ValueError('Duplicate receipt reference; the same receipt cannot be counted twice.')
            total=sum(r['amount_cents'] for r in p['receipts'] if r['award_id']==aid)
            if amount+total>award['amount_cents']: raise ValueError('Receipt exceeds the unrecorded award balance.')
            if p['synthetic'] and not source_ref.startswith('demo:'): raise ValueError('Synthetic records require a demo: source reference.')
            if not p['synthetic'] and source_ref.startswith('demo:'): raise ValueError('Synthetic evidence cannot substantiate a real receipt.')
            p['receipts'].append({'id':str(uuid.uuid4()),'award_id':aid,'amount_cents':amount,'currency':currency,'received_at':dt.isoformat(),'evidence':description,'source_ref':source_ref,'verification_status':'unverified','synthetic':p['synthetic'],'recorded_at':timestamp().isoformat()})
            self._write(con,p)
        return p
    def ledger(self):
        plans=self.all()
        result={'plans':plans,'currency':'USD','verified_received_cents':0,'real_awards_recorded_cents':0,'real_receipts_unverified_cents':0,'synthetic_awards_cents':0,'synthetic_receipts_cents':0,'note':'User-entered records are unverified. This local prototype cannot independently confirm a payout. Synthetic records never count as real money.'}
        for p in plans:
            prefix='synthetic' if p['synthetic'] else 'real'
            result['synthetic_awards_cents' if p['synthetic'] else 'real_awards_recorded_cents']+=sum(a['amount_cents'] for a in p['awards'])
            result['synthetic_receipts_cents' if p['synthetic'] else 'real_receipts_unverified_cents']+=sum(r['amount_cents'] for r in p['receipts'])
        return result

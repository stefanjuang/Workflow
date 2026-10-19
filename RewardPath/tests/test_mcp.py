"""Requires a running server; use an isolated REWARDPATH_DB for testing."""
import os
import json
import unittest
import httpx
BASE=os.environ.get('REWARDPATH_TEST_URL','http://127.0.0.1:8765')
PROFILE={'age':30,'country':'US','max_upfront_cents':0,'remote_only':True,'use_ai':True,'allow_human_writing':False}
class MCPTests(unittest.TestCase):
    def setUp(self):
        self.client=httpx.Client(base_url=BASE,trust_env=False,headers={'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-11-25'})
    def tearDown(self):self.client.close()
    def call(self,method,params):return self.client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':method,'params':params})
    def tool(self,name,args=None):
        result=self.call('tools/call',{'name':name,'arguments':args or {}}).json()['result']
        if not result.get('isError') and 'structuredContent' not in result:
            texts=[x['text'] for x in result.get('content',[]) if x.get('type')=='text']
            self.assertEqual(len(texts),1)
            result['structuredContent']=json.loads(texts[0])
        return result
    def test_handshake_and_tools(self):
        r=self.call('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'test','version':'1'}})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['result']['protocolVersion'],'2025-11-25')
        n=self.client.post('/mcp',json={'jsonrpc':'2.0','method':'notifications/initialized'})
        self.assertEqual(n.status_code,202)
        names=[t['name'] for t in self.call('tools/list',{}).json()['result']['tools']]
        self.assertEqual(len(names),8)
        r=self.tool('list_opportunities');self.assertIn('opportunities',r['structuredContent'])
    def test_version_negotiation(self):
        r=self.call('initialize',{'protocolVersion':'1900-01-01','capabilities':{},'clientInfo':{'name':'test','version':'1'}})
        self.assertEqual(r.json()['result']['protocolVersion'],'2025-11-25')
        r=self.client.post('/mcp',headers={'MCP-Protocol-Version':'1900-01-01'},json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
        self.assertEqual(r.status_code,400)
    def test_origin_host(self):
        for headers in [{'Origin':'https://evil.example'},{'Host':'evil.example'}]:
            r=self.client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
            self.assertEqual(r.status_code,403)
    def test_roundtrip(self):
        r=self.tool('create_plan',{'opportunity_ids':['demo-review'],'profile':PROFILE})
        p=r['structuredContent'];pid=p['id']
        r=self.tool('record_award',{'plan_id':pid,'opportunity_id':'demo-review','amount_cents':3000,'currency':'USD','evidence_description':'Synthetic','source_reference':'demo:integration-award'})
        self.assertTrue(r['isError'])
        for ob in p['obligations']:
            r=self.tool('update_obligation',{'plan_id':pid,'obligation_id':ob['id'],'evidence_description':'Synthetic integration evidence'})
            self.assertFalse(r.get('isError',False))
        r=self.tool('record_award',{'plan_id':pid,'opportunity_id':'demo-review','amount_cents':True,'currency':'USD','evidence_description':'Synthetic','source_reference':'demo:integration-award'})
        self.assertTrue(r['isError'])
        r=self.tool('get_ledger');self.assertEqual(r['structuredContent']['verified_received_cents'],0)
    def test_bad_tool_inputs(self):
        r=self.tool('evaluate_eligibility',{'opportunity_id':'not-real','profile':PROFILE});self.assertTrue(r['isError'])
        r=self.tool('create_plan',{'opportunity_ids':['demo-unclear'],'profile':PROFILE});self.assertTrue(r['isError'])
if __name__=='__main__':unittest.main()

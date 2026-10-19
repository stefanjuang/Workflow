"""Dependency-free local MCP2025-11-25 Streamable HTTP server for the same tools."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,os,mimetypes
import tool_functions as tf
ROOT=Path(__file__).parent
PORT=int(os.environ.get('REWARDPATH_PORT','8765'))
SCHEMAS=json.loads((ROOT/'tool_schemas.json').read_text())
FUNCTIONS={t['name']:getattr(tf,t['name']) for t in SCHEMAS}
class Handler(BaseHTTPRequestHandler):
 def respond(self,status,obj=None,kind='application/json'):
  body=b'' if obj is None else (obj if isinstance(obj,bytes) else json.dumps(obj).encode())
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'");self.end_headers();self.wfile.write(body)
 def allowed(self):
  if self.headers.get('Host','').split(':')[0] not in ('localhost','127.0.0.1'):self.respond(403,{'error':'Loopback only'});return False
  origin=self.headers.get('Origin')
  if origin and origin not in (f'http://localhost:{PORT}',f'http://127.0.0.1:{PORT}'):self.respond(403,{'error':'Origin denied'});return False
  return True
 def do_DELETE(self):
  if self.allowed():self.respond(405,{'error':'Stateless server: session deletion not offered'})
 def do_OPTIONS(self):
  if self.allowed():self.respond(405,{'error':'Cross-origin requests not offered'})
 def do_GET(self):
  if not self.allowed():return
  path=self.path.split('?')[0]
  if path=='/mcp':return self.respond(405,{'error':'SSE stream not offered'})
  if path=='/health':return self.respond(200,{'status':'ok','protocol':'2025-11-25','local_only':True})
  files={'/':'static/index.html','/static/app.js':'static/app.js','/static/style.css':'static/style.css'}
  if path not in files:return self.respond(404,{'error':'Not found'})
  f=ROOT/files[path];return self.respond(200,f.read_bytes(),mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
 def do_POST(self):
  if not self.allowed():return
  if self.path!='/mcp':return self.respond(404,{'error':'Not found'})
  if self.headers.get('MCP-Protocol-Version','2025-11-25')!='2025-11-25':return self.respond(400,{'error':'Unsupported protocol'})
  if 'application/json' not in self.headers.get('Content-Type',''):return self.respond(415,{'error':'JSON required'})
  accept=self.headers.get('Accept','')
  if 'application/json' not in accept or 'text/event-stream' not in accept:return self.respond(406,{'error':'Accept both JSON and event-stream'})
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=1000000:return self.respond(413,{'error':'Invalid body size'})
   q=json.loads(self.rfile.read(length))
   if not isinstance(q,dict) or q.get('jsonrpc')!='2.0':raise ValueError()
  except (ValueError,UnicodeError):return self.respond(400,{'jsonrpc':'2.0','error':{'code':-32700,'message':'Invalid JSON-RPC'}})
  if 'id' not in q:return self.respond(202)
  out={'jsonrpc':'2.0','id':q['id']};m=q.get('method');params=q.get('params') or {}
  if m=='initialize':out['result']={'protocolVersion':'2025-11-25','capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'RewardPath','version':'1.0.0'}}
  elif m=='ping':out['result']={}
  elif m=='tools/list':out['result']={'tools':SCHEMAS}
  elif m=='tools/call':
   try:
    if not isinstance(params,dict) or params.get('name') not in FUNCTIONS:raise ValueError('Unknown tool')
    arguments=params.get('arguments',{})
    if not isinstance(arguments,dict):raise ValueError('Arguments must be object')
    result=FUNCTIONS[params['name']](**arguments)
    out['result']={'content':[{'type':'text','text':json.dumps(result)}],'structuredContent':result,'isError':False}
   except (ValueError,TypeError,KeyError) as e:out['result']={'content':[{'type':'text','text':str(e)}],'isError':True}
  else:out['error']={'code':-32601,'message':'Unknown method'}
  self.respond(200,out)
if __name__=='__main__':
 print(f'RewardPath local MCP: http://127.0.0.1:{PORT}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()

"""Loopback-only, local HTTP + MCP application. No external API calls."""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from pydantic import StrictInt
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from domain import CATALOG, Store, evaluate, compare

ROOT=Path(__file__).parent
PORT=int(os.environ.get('REWARDPATH_PORT','8765'))
store=Store()
mcp=FastMCP('RewardPath',instructions='Evaluate evidence-linked opportunities and record only user-supplied evidence. No tool redeems offers or pays money. Synthetic examples are not available rewards.',json_response=True,stateless_http=True,streamable_http_path='/mcp',host='127.0.0.1',port=PORT,transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,allowed_hosts=['127.0.0.1:*','localhost:*'],allowed_origins=[f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}']))

@mcp.tool()
def list_opportunities() -> dict:
    """Return a bounded catalog. Synthetic examples are not real reward offers."""
    return {'opportunities':CATALOG,'catalog_checked_at':'2026-10-19','notice':'Public facts must be rechecked before entry. Synthetic fixtures demonstrate the planner only.'}

@mcp.tool()
def evaluate_eligibility(opportunity_id: str, profile: dict) -> dict:
    """Check eligibility as pass/fail/unknown. Missing facts cannot become pass."""
    return evaluate(opportunity_id,profile)

@mcp.tool()
def compare_plans(opportunity_ids: list[str], profile: dict) -> dict:
    """Check compatibility, prerequisites and zero-spend constraints; never infer win odds."""
    return compare(opportunity_ids,profile)

@mcp.tool()
def create_plan(opportunity_ids: list[str], profile: dict) -> dict:
    """Create only a compatible, eligible local plan. This does not enroll or submit anywhere."""
    return store.create(opportunity_ids,profile)

@mcp.tool()
def update_obligation(plan_id: str, obligation_id: str, evidence_description: str = '') -> dict:
    """Mark an ordered local obligation complete. Submission steps require evidence."""
    return store.update(plan_id,obligation_id,evidence_description)

@mcp.tool()
def record_award(plan_id: str, opportunity_id: str, amount_cents: StrictInt, currency: str, evidence_description: str, source_reference: str) -> dict:
    """Record an unverified award after submission. An award is not a payout."""
    return store.award(plan_id,opportunity_id,amount_cents,currency,evidence_description,source_reference)

@mcp.tool()
def record_receipt(plan_id: str, award_id: str, amount_cents: StrictInt, currency: str, received_at: str, evidence_description: str, source_reference: str) -> dict:
    """Record evidence of a claimed receipt, always unverified; never fabricate payment confirmation."""
    return store.receipt(plan_id,award_id,amount_cents,currency,received_at,evidence_description,source_reference)

@mcp.tool()
def get_ledger() -> dict:
    """Separate synthetic, reported and independently verified money. No verification is claimed."""
    return store.ledger()

mcp_app=mcp.streamable_http_app()
@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield
app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

@app.middleware('http')
async def local_security(request: Request,call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ('localhost','127.0.0.1'):
        return JSONResponse({'error':'Loopback hosts only.'},status_code=403)
    origin=request.headers.get('origin')
    if origin and origin not in (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):
        return JSONResponse({'error':'Origin is not allowed.'},status_code=403)
    if request.url.path.startswith('/mcp'):
        protocol=request.headers.get('mcp-protocol-version')
        if protocol and protocol!='2025-11-25':
            return JSONResponse({'error':'Unsupported MCP-Protocol-Version.'},status_code=400)
        if int(request.headers.get('content-length','0'))>1_000_000:
            return JSONResponse({'error':'Request too large.'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"
    return response

@app.get('/')
def home(): return FileResponse(ROOT/'static/index.html')
@app.get('/health')
def health(): return {'status':'ok','protocol':'2025-11-25','local_only':True}
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
app.mount('/',mcp_app)

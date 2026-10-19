from domain import CATALOG,Store,evaluate,compare
StrictInt=int
store=Store()

def list_opportunities() -> dict:
    """Return a bounded catalog. Synthetic examples are not real reward offers."""
    return {'opportunities': CATALOG, 'catalog_checked_at': '2026-10-19', 'notice': 'Public facts must be rechecked before entry. Synthetic fixtures demonstrate the planner only.'}

def evaluate_eligibility(opportunity_id: str, profile: dict) -> dict:
    """Check eligibility as pass/fail/unknown. Missing facts cannot become pass."""
    return evaluate(opportunity_id, profile)

def compare_plans(opportunity_ids: list[str], profile: dict) -> dict:
    """Check compatibility, prerequisites and zero-spend constraints; never infer win odds."""
    return compare(opportunity_ids, profile)

def create_plan(opportunity_ids: list[str], profile: dict) -> dict:
    """Create only a compatible, eligible local plan. This does not enroll or submit anywhere."""
    return store.create(opportunity_ids, profile)

def update_obligation(plan_id: str, obligation_id: str, evidence_description: str='') -> dict:
    """Mark an ordered local obligation complete. Submission steps require evidence."""
    return store.update(plan_id, obligation_id, evidence_description)

def record_award(plan_id: str, opportunity_id: str, amount_cents: StrictInt, currency: str, evidence_description: str, source_reference: str) -> dict:
    """Record an unverified award after submission. An award is not a payout."""
    return store.award(plan_id, opportunity_id, amount_cents, currency, evidence_description, source_reference)

def record_receipt(plan_id: str, award_id: str, amount_cents: StrictInt, currency: str, received_at: str, evidence_description: str, source_reference: str) -> dict:
    """Record evidence of a claimed receipt, always unverified; never fabricate payment confirmation."""
    return store.receipt(plan_id, award_id, amount_cents, currency, received_at, evidence_description, source_reference)

def get_ledger() -> dict:
    """Separate synthetic, reported and independently verified money. No verification is claimed."""
    return store.ledger()

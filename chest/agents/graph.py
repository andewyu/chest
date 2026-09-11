"""The Chest agent graph.

    Forecaster -> Scout -> Eligibility Screener -> Drafter -> Compliance Reviewer

Five agents, one direction, one human approval boundary at the end. Each agent has a
narrow job and hands a typed payload to the next; nothing here is a general
"do the thing" prompt.

The current approval is persisted application state: the reviewer drafts and
the human replies YES or EDIT. A resumable Strands protocol-level interrupt is
planned, but this build does not claim to implement one.

The whole graph is built per account: the tools close over that account's
ledger and the prompts carry that account's eligibility profile, so a draft
written for one org can only ever cite that org's entries.
"""
from __future__ import annotations

from strands import Agent, tool
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder

from chest.agents.voice import compose
from chest.config import BEDROCK_MODEL_ID, CHEST_FAKE_MODEL
from chest.store.accounts import Account
from chest.store.ledger import LedgerStore
from chest.tools import forecast as fc
from chest.tools import grants_gov
from chest.tools.provenance import enforce_provenance, validate_draft


def _model():
    if CHEST_FAKE_MODEL:
        from chest.agents.fake_model import FakeModel

        return FakeModel(model_id=BEDROCK_MODEL_ID)
    return BedrockModel(model_id=BEDROCK_MODEL_ID)


# --------------------------------------------------------------------------
# Tools — built per account, closed over that account's ledger
# --------------------------------------------------------------------------

def _tools(account: Account):
    store = LedgerStore(account.id)

    @tool
    def run_forecast(horizon_days: int = 365) -> dict:
        """Project the org's balance forward and return the dollar gap with evidence."""
        gap = fc.forecast(store, horizon_days=horizon_days)
        return {
            "gap_amount": gap.amount,
            "goes_negative_on": gap.goes_negative_on,
            "current_balance": gap.current_balance,
            "monthly_net": gap.monthly_net,
            "evidence": gap.evidence,
            "summary": gap.summary(),
        }

    @tool
    def find_grants_for_gap(gap_amount: float, limit: int = 5) -> list[dict]:
        """Return posted federal opportunities whose award range brackets the gap."""
        hits = grants_gov.match_gap(gap_amount)[:limit]
        return [
            {
                "id": o.id,
                "title": o.title,
                "agency": o.agency,
                "award_floor": o.award_floor,
                "award_ceiling": o.award_ceiling,
                "close_date": o.close_date,
                "applicant_types": o.applicant_types,
                "url": o.url,
            }
            for o in hits
        ]

    @tool
    def opportunity_detail(opportunity_id: str) -> dict:
        """Full text and eligibility criteria for one opportunity."""
        o = next((x for x in grants_gov.load_cache() if x.id == str(opportunity_id)), None)
        if o is None:
            o = grants_gov.fetch(opportunity_id)
        return o.__dict__ if o else {}

    @tool
    def ledger_entries(kind: str = "") -> list[dict]:
        """Posted ledger entries, optionally filtered by kind. Each carries its id
        so any figure in a draft can cite the line it came from."""
        entries = store.posted()
        if kind:
            entries = [e for e in entries if e.kind == kind]
        return [
            {"id": e.id, "date": e.occurred_on, "amount": e.amount,
             "kind": e.kind, "memo": e.memo}
            for e in entries
        ]

    @tool
    def validate_draft_provenance(draft: str) -> dict:
        """Verify every dollar figure against this account's posted entries."""
        entry_ids = {entry.id for entry in store.posted()}
        report = validate_draft(draft, entry_ids)
        return {"valid": report.valid, "violations": report.violations}

    return (
        run_forecast,
        find_grants_for_gap,
        opportunity_detail,
        ledger_entries,
        validate_draft_provenance,
    )


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------

def build_agents(account: Account) -> dict[str, Agent]:
    """The five agents, wired to one account's books and eligibility profile."""
    (
        run_forecast,
        find_grants_for_gap,
        opportunity_detail,
        ledger_entries,
        validate_draft_provenance,
    ) = _tools(account)
    org = account.profile()
    model = _model()

    forecaster = Agent(
        model=model,
        name="forecaster",
        system_prompt=(
            "You are Chest's Forecaster. Call run_forecast and report the dollar gap "
            "and the date it becomes real, in one or two sentences. Always list the "
            "ledger entry ids that drive the projection. If there is no shortfall, "
            "say so plainly and stop — do not invent one."
        ),
        tools=[run_forecast],
    )

    scout = Agent(
        model=model,
        name="scout",
        system_prompt=(
            "You are Chest's Scout. You are given a dollar gap. Call find_grants_for_gap "
            "with that exact amount. The gap is the query — do not substitute mission "
            "keywords for it. Return the candidates with their award ranges and close "
            "dates. Do not evaluate fit; that is the Screener's job."
        ),
        tools=[find_grants_for_gap],
    )

    screener = Agent(
        model=model,
        name="eligibility_screener",
        system_prompt=(
            f"You are Chest's Eligibility Screener for {org.name} "
            f"(applicant type: {org.applicant_type}; annual budget "
            f"${org.annual_budget:,.0f}; state: {org.state}). "
            "For each candidate, call opportunity_detail and check applicant type, "
            "org size, and stated restrictions using only the published record. Never "
            "infer an unstated requirement. If the synopsis defers eligibility to an "
            "attachment, flag that for human verification. Reject anything the org plainly "
            "cannot win and say why in one line. Pass forward at most one opportunity: "
            "the best fit. Nobody's time gets spent drafting until you've done this."
        ),
        tools=[opportunity_detail],
    )

    drafter = Agent(
        model=model,
        name="drafter",
        system_prompt=(
            f"You are Chest's Drafter, writing for {org.name}. Write the narrative and "
            "budget-justification sections for the selected opportunity. Call "
            "ledger_entries for every figure you use. RULE: every dollar amount in the "
            "draft must be followed by the ledger entry id it came from, like "
            "$1,240.00 [a3f19c2b]. Never state a figure you cannot cite. Write plainly — "
            "the reader is a program officer, and the person approving this is a "
            "volunteer with a day job."
        ),
        tools=[ledger_entries, opportunity_detail],
    )

    # The Reviewer is the only graph agent a human reads, so it is the only one
    # that speaks in Chest's voice. The four upstream agents talk to each other
    # and stay clinical.
    reviewer = Agent(
        model=model,
        name="compliance_reviewer",
        system_prompt=compose(
            "You are Chest's Compliance Reviewer, and the last stop before a human "
            "reads anything. Call validate_draft_provenance on the complete draft. "
            "If it reports any violation, block the draft and list what must be "
            "corrected; never present it as ready. Check the draft against the opportunity's stated "
            "requirements: required sections, page and word limits, deadline, "
            "eligibility. Flag every uncited dollar figure as a blocker.",
            extra=(
                "OUTPUT SHAPE\n\n"
                "Open with one line the treasurer can read on a phone: what this is, "
                "what it's worth, when it closes. That line is the only casual thing "
                "here — a grant draft is register 3, so the rest is careful and "
                "complete.\n\n"
                "Every dollar amount anywhere in your response, including that "
                "summary, must carry a valid ledger citation. Then any blockers you "
                "found, one per line, plain. Then the draft "
                "itself, verbatim and unedited: it is going to a program officer and "
                "it keeps its own formal voice. Do not rewrite the draft in your own "
                "voice.\n\n"
                "End with exactly: 'Reply YES to approve this draft, or EDIT to tell "
                "me what to change.'\n\n"
                "Chest never submits an application. Do not imply that it might."
            ),
        ),
        tools=[validate_draft_provenance, opportunity_detail],
    )

    return {
        "forecaster": forecaster,
        "scout": scout,
        "screener": screener,
        "drafter": drafter,
        "reviewer": reviewer,
    }


def build_graph(account: Account):
    """Wire the five agents into a Strands graph for one account."""
    agents = build_agents(account)
    b = GraphBuilder()
    for name, agent in agents.items():
        b.add_node(agent, name)

    b.add_edge("forecaster", "scout")
    b.add_edge("scout", "screener")
    b.add_edge("screener", "drafter")
    b.add_edge("drafter", "reviewer")

    b.set_entry_point("forecaster")
    # Bound both spend and wall-clock time. The graph is linear today, so five
    # node executions is exactly one complete Gap-to-Grant pass.
    # https://strandsagents.com/docs/api/python/strands.multiagent.graph/#set-max-node-executions
    b.set_max_node_executions(5)
    b.set_execution_timeout(300)
    b.set_node_timeout(90)
    return b.build()


_GRAPHS: dict[str, object] = {}


def get_graph(account: Account):
    """One built graph per account, reused across sweeps."""
    if account.id not in _GRAPHS:
        _GRAPHS[account.id] = build_graph(account)
    return _GRAPHS[account.id]


def reviewer_output(result) -> str:
    """Return only the final reviewed node, never internal chain-of-work output."""
    node_result = result.results.get("reviewer")
    if node_result is None or not str(node_result).strip():
        raise RuntimeError("grant graph did not produce a reviewed draft")
    return str(node_result).removesuffix("\n")


def run_gap_to_grant(account: Account, gap_amount: float, goes_negative_on: str) -> str:
    """Run the graph and return only output that passes the provenance gate."""
    result = get_graph(account)(
        f"The org is projected ${gap_amount:,.0f} short by {goes_negative_on}. "
        "Find and draft the grant that closes it."
    )
    entry_ids = {entry.id for entry in LedgerStore(account.id).posted()}
    return enforce_provenance(reviewer_output(result), entry_ids)

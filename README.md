# Chest 🧰

**AI treasurer + grant agent for small volunteer-run nonprofits.**

Chest watches a small nonprofit's real finances, forecasts the exact dollar gap before it hurts, and goes and finds — and drafts — the grant sized to close it. The whole product is a chat thread. No app, no dashboard, no login.

> Chest doesn't just track your money. It goes and finds the money you're missing.

Built for the **AWS "Agents for Humans" Hackathon — Good Neighbor Agents Track**, on the **Strands Agents SDK**.

---

## The problem

- U.S. foundations gave out **$117.15 billion in 2025** (Giving USA / Candid).
- Nonprofits under $50K annual revenue are **~60% of all U.S. nonprofits but capture only ~0.4% of foundation grant dollars** (Candid, 2019–2023).
- Of the ~9% of small orgs that skip applying for grants entirely, **over half say it's because they lack the staff or time** to find and apply.

The money exists. The smallest orgs — run by a volunteer treasurer with a day job — can't reach it.

## The mechanic: the Gap-to-Grant loop

1. **Detect** — forecast the balance forward from logged transactions; output a dollar gap and the date it becomes real.
2. **Match** — search for grants whose award range *brackets that exact gap* (`awardFloor ≤ gap ≤ awardCeiling`), not generic keyword hits.
3. **Draft** — write the application using real ledger numbers, with visible provenance (which ledger line produced which figure).
4. **Ask** — send a one-line summary and the draft. Reply **YES** to approve, **EDIT** to revise.

**There is no fifth step. The agent never submits.**

## What's defensible here

Grant tools match on mission. Finance tools forecast shortfalls. No product we found uses the **forecasted dollar gap itself as the retrieval key**, grounds the draft in the organization's live ledger, and meets a volunteer treasurer where they already are — a text thread.

(We do *not* claim nobody connects budget monitoring to grant discovery. Instrumentl markets accounting-connection + AI matching + writing; GrantFlow ships runway forecasting. The narrow claim above is the one that holds.)

## Architecture

```
EventBridge Scheduler (background sweep, no human trigger)
        │
        ▼
┌───────────────────────────────────────────────────┐
│  Strands multi-agent graph, on AgentCore Runtime  │
│                                                   │
│  Forecaster → Scout → Eligibility Screener →      │
│  Drafter → Compliance Reviewer                    │
└───────────────────────────────────────────────────┘
        │                              │
        ▼                              ▼
  Ledger store (DynamoDB)     interrupt() → WhatsApp/Telegram/iMessage
  balances, dues, history     "Reply YES to approve / EDIT"
```

| Agent | Job |
|---|---|
| **Forecaster** | Projects balance forward, outputs a dollar gap and the date it bites |
| **Scout** | Queries Grants.gov for opportunities whose award range brackets the gap |
| **Eligibility Screener** | Checks EIN, org age, budget size, applicant type before anyone drafts |
| **Drafter** | Writes narrative + budget justification from real ledger figures, with provenance |
| **Compliance Reviewer** | Checks the draft against the opportunity's stated requirements |

Human-in-the-loop is a Strands `interrupt()` at the protocol level — not an `if` statement in app code.

### Stack

| Layer | Choice |
|---|---|
| Input channel | Twilio WhatsApp Sandbox webhook / Telegram Bot API / iMessage via [Blooio](https://blooio.com) (see honesty note below) |
| Orchestration | Strands Agents SDK, multi-agent graph (`GraphBuilder`) |
| Runtime | Amazon Bedrock AgentCore Runtime |
| Memory | AgentCore Memory (donor names, past rejections, recurring expenses) |
| Identity | AgentCore Identity |
| Observability | AgentCore Observability / OpenTelemetry traces |
| Grant data | Grants.gov `search2` + `fetchOpportunity` (keyless) |
| Receipt OCR (optional) | Amazon Textract `AnalyzeExpense` |

## Honesty section

We'd rather disclose a constraint than have a judge discover it.

- **The agent never submits a grant application.** Grants.gov submission legally requires a human Authorized Organization Representative with SAM.gov registration, and NIH policy (NOT-OD-25-132) excludes applications substantially developed by AI. Chest drafts; a human approves and files. This is a trust feature.
- **Channel:** the agent is channel-agnostic. US SMS requires A2P 10DLC carrier registration that takes 10–15 days, so that's still roadmap. Apple itself provides no public iMessage send API — full stop. The demo's iMessage channel runs through **[Blooio](https://blooio.com)**, a third-party relay service that operates real Apple infrastructure to deliver blue-bubble messages; it is **not** an Apple-sanctioned integration, and we say so on stage. The Twilio WhatsApp Sandbox and Telegram channels remain the standard, no-relay-dependency demo path and hit the identical webhook handler.
- **Data:** federal opportunities shown are **real and live** from Grants.gov. Foundation/private grant data (Candid) is paywalled at $219+/month — it's a paid-tier roadmap item, not something we faked.
- Every dollar figure in a generated draft traces to a specific ledger entry.

## Competitive landscape

| Tool | What it does | Gap vs. Chest |
|---|---|---|
| Instrumentl | AI grant matching + writing + accounting connection | No gap-triggered (dollar-sized) matching; not chat-native |
| Grantable, Vee, Granted AI, Grant Assistant | AI grant discovery + drafting | Match on mission/profile, not a live forecasted dollar gap |
| GrantFlow | Cash forecasting, funding-gap alerts | No grant discovery layer |
| Bonterra Que, Blackbaud Development Agent | Agentic nonprofit platforms | Enterprise-oriented, not chat-first, not priced for sub-$50K orgs |
| AlignMint (Minty) | Free nonprofit AI accounting via chat | Read-only by design; refuses to create/update records |
| Sage/Fyle, MoneyFeed | SMS/WhatsApp expense logging | Not nonprofit-specific, no grant layer |

## Roadmap (explicitly not in this build)

Grant submission · voice memo logging · bank/Plaid reconciliation · officer handoff mode · board PDF reports · win-likelihood scoring · warm-intro surfacing · rejection learning loop · foundation grant data · 990-N e-filing.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in your keys

python -m scripts.seed_ledger        # seed a demo nonprofit's ledger
python -m scripts.cache_grants       # cache ~250 live Grants.gov opportunities
python -m chest.channels.webhook     # run the chat webhook locally
```

The webhook serves all three channels at once (`/whatsapp`, `/telegram`, `/imessage`).
Set `CHEST_CHANNEL` in `.env` to pick which one the background sweep (`scripts/sweep.py`)
notifies over. For iMessage, sign up at [blooio.com](https://blooio.com), set
`BLOOIO_API_KEY` / `BLOOIO_WEBHOOK_SECRET` / `BLOOIO_FROM_NUMBER`, and register
`<ngrok-url>/imessage` as the webhook URL in the Blooio dashboard.

See [PLAN.md](PLAN.md) for the four-day build plan.

## License

MIT

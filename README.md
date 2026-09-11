# Chest 🧰

**AI treasurer + grant agent for small volunteer-run nonprofits.**

Chest watches a small nonprofit's real finances, forecasts the exact dollar gap before it hurts, and goes and finds — and drafts — the grant sized to close it. Sign your org up once on a web page, text the code to the bot, and everything after that is a text thread. No app to install, nothing to learn.

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

## Multi-tenant by construction

Any organization can sign up and gets its own books. That isolation is a
property of the code's shape rather than a filter someone has to remember:

```
web signup ──> Account (org profile + 8-char link code)
                  │
   text the code ─┤
                  ▼
   "telegram:12345" ──> AccountStore.account_for ──> Account
                                                       │
                              ┌────────────────────────┴───────────────────────┐
                              ▼                                                ▼
                    LedgerStore(account_id)                     Agent built per account
                    its own file / partition                    tools closed over that ledger
```

- An unlinked phone can send exactly one thing: a link code. It never reaches
  an agent, a ledger, or a model call.
- The treasurer's tools are constructed inside `_tools(account)` and close over
  one `LedgerStore`. The model has no argument it can pass to reach another
  org's money — isolation is what the tool can *reach*, not a rule in a prompt.
- The grant graph is built per account too, so a draft can only cite the ledger
  entries of the org it was written for.
- `tests/test_accounts.py` holds that line, including the obvious attack: paste
  another org's entry id into your own thread and confirm it.

## Architecture

```
EventBridge Scheduler (background sweep — every account, no human trigger)
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
  Ledger store, per account      approval prompt → chat channels
  balances, dues, history     "Reply YES to approve / EDIT"
```

| Agent | Job |
|---|---|
| **Forecaster** | Projects balance forward, outputs a dollar gap and the date it bites |
| **Scout** | Queries Grants.gov for opportunities whose award range brackets the gap |
| **Eligibility Screener** | Checks published applicant type, budget/size, geography, and restrictions; flags attachment-only rules for a human |
| **Drafter** | Writes narrative + budget justification from real ledger figures, with provenance |
| **Compliance Reviewer** | Checks the draft against the opportunity's stated requirements |

Human approval is explicit and Chest has no grant-submission tool. A resumable
Strands protocol-level `interrupt()` is still planned; the current build must
not be described as having that feature yet.

### Stack

| Layer | Choice |
|---|---|
| Input channel | Twilio WhatsApp Sandbox webhook / Telegram Bot API / iMessage via [Blooio](https://blooio.com) (see honesty note below) |
| Orchestration | Strands Agents SDK, multi-agent graph (`GraphBuilder`) |
| Runtime | Amazon Bedrock AgentCore Runtime |
| Memory | Strands snapshot sessions locally; AgentCore Memory is planned |
| Identity | Signed channel webhooks; AgentCore Identity is planned |
| Observability | OpenTelemetry instrumentation, visible after AgentCore deployment |
| Grant data | Grants.gov `search2` + `fetchOpportunity` (keyless) |
| Receipt OCR (optional) | Amazon Textract `AnalyzeExpense` |

## Honesty section

We'd rather disclose a constraint than have a judge discover it.

- **The agent never submits a grant application.** Grants.gov submission legally requires a human Authorized Organization Representative with SAM.gov registration, and NIH policy (NOT-OD-25-132) excludes applications substantially developed by AI. Chest drafts; a human approves and files. This is a trust feature.
- **Channel:** the agent is channel-agnostic. US SMS requires A2P 10DLC carrier registration that takes 10–15 days, so that's still roadmap. Apple itself provides no public iMessage send API — full stop. The demo's iMessage channel runs through **[Blooio](https://blooio.com)**, a third-party relay service that operates real Apple infrastructure to deliver blue-bubble messages; it is **not** an Apple-sanctioned integration, and we say so on stage. The Twilio WhatsApp Sandbox and Telegram channels remain the standard, no-relay-dependency demo path and hit the identical webhook handler.
- **Data:** federal opportunities are retrieved from the live Grants.gov API and
  cached before a demo for reliability. The checked-in snapshot and its refresh
  date are documented in `data/README.md`. Foundation/private grant data
  (Candid) is paywalled at $219+/month — it is a paid-tier roadmap item, not
  something we faked.
- Every dollar figure in a generated draft traces to a specific ledger entry.
- **There are no passwords yet.** A link code binds a phone to an org, and the
  dashboard URL is a capability link: whoever holds it can read those books.
  That is the right amount of auth for a hackathon demo and the wrong amount
  for real donor data, so the app says so on the page instead of implying a
  login exists. Real auth is a roadmap item, not a claim we're making.

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

Requires **Python 3.10 or newer**. On macOS, check `python3 --version` before
creating the environment; the system Python may still be 3.9 and cannot install
current Strands releases.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in your keys
```

Check that the model actually works before anything else:

```bash
python scripts/check_model.py
```

It makes one real Bedrock call and, when it fails, names the thing you have to
go do — the Anthropic use-case form, a missing `us.` inference-profile prefix,
a retired model version, or absent credentials.

Then start the demo:

```bash
python -m scripts.run_demo
```

One command brings up the signup page and the Telegram bot together. It makes a
real Bedrock call first and runs live if that works; if it doesn't, it prints
why and falls back to the offline stand-in, loudly, because a rule-based
stand-in must never be mistaken for the model on stage. `--real` refuses to
start without Bedrock, which is what you want before presenting.

Or run the two halves yourself. Signup page:

```bash
uvicorn chest.channels.webhook:app --reload --port 8000
```

Telegram, with no tunnel and no ngrok:

```bash
python -m scripts.telegram_poll
```

Open <http://localhost:8000>, create an org, and text the 8-character code to
the bot. That's the whole onboarding.

For deployment the same handler runs behind webhooks instead — the app serves
all three channels at once (`/whatsapp`, `/telegram`, `/imessage`), so put it
on a public URL and register that with Telegram's `setWebhook`, Twilio, or
Blooio. For iMessage, sign up at [blooio.com](https://blooio.com) and set
`BLOOIO_API_KEY` / `BLOOIO_WEBHOOK_SECRET` / `BLOOIO_FROM_NUMBER`. Set
`PUBLIC_URL` so the code the bot hands out points somewhere a phone can open.

### Testing without a model, or without a phone

```bash
CHEST_FAKE_MODEL=1 python scripts/smoke_chat.py       # log -> confirm -> post
CHEST_FAKE_MODEL=1 python scripts/smoke_chat.py --sessions   # two orgs don't mix
CHEST_FAKE_MODEL=1 python scripts/replay_webhook.py   # the whole inbound path
pytest                                                # isolation + voice
```

`CHEST_FAKE_MODEL=1` swaps in a rule-based stand-in so the plumbing runs with
no model access. It proves the pipes, never the judgment — see the note at the
top of `chest/agents/fake_model.py`. `replay_webhook.py` signs two orgs up over
HTTP, links a phone to each, and POSTs the exact payloads Telegram, Twilio and
Blooio send, against a throwaway ledger.

Other scripts: `scripts/seed_ledger.py` (sample books for an account),
`scripts/cache_grants.py` (~250 live Grants.gov opportunities),
`scripts/sweep.py` (the background run), `scripts/migrate_accounts.py`
(lift a pre-accounts ledger into an account).

All webhook channels fail closed when their configured signing secret is
missing or invalid. Telegram replies are split safely when a reviewed draft
exceeds the platform's single-message limit.

See [PLAN.md](PLAN.md) for the four-day build plan and
[docs/deployment.md](docs/deployment.md) for the prepared AgentCore deployment path.

## License

MIT

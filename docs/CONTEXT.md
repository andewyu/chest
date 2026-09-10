# Chest — Project Context
### AI treasurer + grant agent for small volunteer-run nonprofits
Built for the AWS "Agents for Humans" Hackathon — Good Neighbor Agents Track — Strands Agents SDK
Submission deadline: **Monday, September 14, 2026, 5:00 PM PT**

This file is the corrected, build-ready version of the original concept doc. Every stat, claim, and technical detail below has been fact-checked against live sources as of Sept 10, 2026. Where the original doc had a problem, it's fixed here — nothing is carried over unverified.

---

## 1. One-line pitch

Chest is a background AI agent that watches a small nonprofit's real finances, forecasts the exact dollar gap before it hurts, and goes and finds — and drafts — the grant sized to close it. The whole product is a chat thread. No app, no dashboard, no login.

## 2. The problem (verified numbers only)

Use these four. All are checked against primary sources today. Do not reintroduce the old $104B or $4–7B figures — see §7.

1. **U.S. foundations gave out $117.15 billion in 2025** (Giving USA / Candid). Use the current-year number, not the stale $104B figure that circulated for 2023.
2. **The smallest nonprofits (under $50K annual revenue) are roughly 60% of all U.S. nonprofits but capture only about 0.4% of foundation grant dollars** (Candid, 2019–2023 data). This is the strongest, best-verified number — lead with it.
3. **Of the small subset of nonprofits that skip applying for grants entirely (about 9% of small orgs), over half say it's because they lack the staff or time to find and apply.** State it exactly this way — it is NOT "over half of all nonprofits," and overstating it is an easy, embarrassing catch for a judge.
4. Optional supporting context (not required, use only if useful): compliance burden — IRS Form 990-N deadlines and state charitable-registration renewals are a recurring, unglamorous failure point for volunteer treasurers, and missing them can cost an org its tax-exempt status.

**Do not use:** the "$4–7 billion in unclaimed corporate matching gifts" statistic. It has no independent primary source — it traces back only to Double the Donation's own unpublished internal analysis, and every other citation of it just re-cites them. It's also off-thesis (matching gifts are a donor/employer workflow, not a treasurer/grant workflow). Cut it entirely.

## 3. Naming — keeping "Chest," with eyes open

**Decision: keep the name Chest.** Known conflicts, for the record, so nobody on the team is blindsided by a judge's question: an existing iOS app called "Chest – Expense Tracker," a funded UK fintech at joinchest.com, the American College of Chest Physicians, and "chest workout" SEO noise. A US-only hackathon launch reduces the *practical* collision risk (no immediate global trademark exposure, no live storefront conflict to navigate this week) but does not eliminate it — the iOS app is on the same App Store US users browse, and a technical judge could raise it. This is an acceptable, low-stakes bet for a hackathon submission; revisit before any real launch or trademark filing.

Visual identity: warm gold/amber palette, a chest that "opens" on a grant match, taglines like "What's in the Chest?" for a balance check and "Chest found treasure" for a matched grant.

## 4. Positioning

**For:** the volunteer treasurer or board member at a small, under-resourced nonprofit — the person doing this unpaid, on top of a day job, with no finance background.

**Against:** dashboard-first AI bookkeeping tools that require login and setup (Bookeeping.ai, AlignMint), and grant-discovery tools that match on mission keywords instead of the actual dollar amount needed (Instrumentl, Grantable, Vee).

**The real, defensible claim (rewritten from the original — the old wording will not survive a judge's fact-check):**

> Grant tools match on mission. Finance tools forecast shortfalls. No product we found uses the forecasted dollar gap itself as the retrieval key, grounds the draft in the organization's live ledger, and meets a volunteer treasurer where they already are — a text thread.

Do not claim "no existing tool connects budget monitoring to grant discovery" as a blanket statement. It's false: Instrumentl's homepage already markets accounting-system connection plus AI grant matching plus writing together, and GrantFlow already ships shortfall/runway forecasting. The narrow claim above is the one that survives scrutiny.

## 5. Design model: conversational-first (Poke-inspired), channel corrected

Same design philosophy as the original doc, with one hard fix: **drop SMS as a launch channel, and be precise about what "iMessage" means.**

- **Apple itself provides no public API for sending iMessages.** "Messages for Business" requires becoming an Apple-approved Messaging Service Provider — out of scope entirely. That has not changed.
- **iMessage is shipped anyway, via a third-party relay: [Blooio](https://blooio.com).** Blooio operates real Apple infrastructure behind a REST API (`POST /v2/api/chats/{chatId}/messages`, bearer-token auth, inbound delivered as `message.received` webhooks). It delivers genuine blue-bubble iMessages with SMS/RCS fallback. **It is not an Apple-sanctioned integration** — say this explicitly in the pitch and README. Wired in at `chest/channels/webhook.py` (`/imessage` route, `send_blooio()`), gated behind `CHEST_CHANNEL=imessage` and `BLOOIO_API_KEY`.
- **US SMS (Twilio) is still not usable in this timeframe.** As of Sept 2023, Twilio fully blocks all unregistered US 10DLC traffic. A2P 10DLC campaign review takes 10–15 days. Trial accounts cannot register for A2P 10DLC at all. Toll-free verification takes 3–5 business days, which lands after the Sept 14 deadline even if submitted today.
- **Twilio WhatsApp Sandbox and Telegram remain the primary, no-third-party-relay demo path.** No sender registration, available instantly, identical webhook code. Keep at least one of these as the fallback if Blooio has any hiccup on demo day — it's a new paid dependency added late in the build.
- **On stage, say this plainly:** "The agent is channel-agnostic. SMS to US numbers requires carrier registration that takes 10–15 days. iMessage here runs through Blooio, a relay service operating real Apple accounts — not an Apple API, since Apple doesn't publish one. WhatsApp and Telegram run over the identical webhook with no such dependency." Judges respect disclosed constraints and penalize discovered ones.

Everything else from the original design model still holds and is good:
- **Recipes**: pre-built automations ("remind members about dues on the 1st," "send me a Friday balance summary") plus user-authored custom ones in plain English.
- **Proactive nudges, not prompts**: the agent surfaces a shortfall or a matching grant before anyone thinks to ask.
- **Long-term memory**: remembers donor names, past grant rejections, and recurring expenses across conversations.
- **Integrations as extensions, not requirements**: works fully from chat with zero setup; a bank feed or spreadsheet connection is optional, later.
- **Voice memo support**: nice-to-have, not core — see scope cuts in §8.

## 6. The core mechanic — Gap-to-Grant loop (unchanged concept, tightened claim)

1. **Detect** — the agent watches real dues/expense/fundraising data and forecasts a shortfall before it happens (simple linear burn-rate projection is enough for a hackathon).
2. **Match** — it searches specifically for grants whose award range brackets that exact dollar gap (`awardFloor ≤ gap ≤ awardCeiling`), not generic keyword results.
3. **Draft** — it writes the application using real ledger numbers, so budget-justification answers are accurate on the first pass, with visible provenance (which ledger line produced which number).
4. **Ask** — it texts a one-line summary and the draft. Reply **YES** to approve, **EDIT** to revise. **There is no fifth step.** The agent never submits. See §7 on why this is a feature, not a limitation.

Marketing line (still good, keep it): *"Chest doesn't just track your money. It goes and finds the money you're missing."*

## 7. What changed from the original — a straight list of fixes

Read this section once before writing any pitch copy, so nobody on the team accidentally reintroduces a claim that's already been cut.

| Original claim | Problem | Fix |
|---|---|---|
| "$104 billion in foundation grants" | Stale — 2023 figure | Use **$117.15B (2025)** |
| "$4–7B in unclaimed matching gifts" | No independent primary source; off-thesis | **Deleted entirely** |
| "Over half of nonprofits that skip grants lack staff/time" | Actually over half of the ~9% who skip grants, not over half of all nonprofits | Restated precisely (§2, item 3) |
| "No existing tool connects budget monitoring to grant discovery and drafting" | False as a blanket claim — Instrumentl and GrantFlow already do adjacent versions | Narrowed to the gap-as-retrieval-key claim (§4) |
| "It texts a one-line summary and the draft — reply YES to submit" | Grants.gov submission legally requires a human Authorized Organization Representative with SAM.gov registration; NIH explicitly will not consider applications substantially developed by AI (NOT-OD-25-132), with post-award referral to research integrity | **"YES" now means approve the draft, not submit it.** The agent never submits anything. State this as a deliberate safety design, not a missing feature. |
| Delivered over "iMessage, SMS, WhatsApp, and Telegram" | No *Apple* iMessage API exists; US SMS is carrier-blocked for the timeline | Launch channels are **WhatsApp Sandbox + Telegram** (no third-party dependency) plus **iMessage via Blooio** (a disclosed third-party relay). SMS stays roadmap. |
| Name: "Chest" | Collides with an existing iOS app of the same name, a UK fintech, and unwinnable SEO | **Kept as Chest** — acceptable risk for a US-only hackathon launch (see §3) |
| Single router agent + two sub-agents | Technically thin — every judge will have seen this orchestration pattern | Upgraded to a real 5-agent Strands graph (§9) |

## 8. Realistic 4-day feature scope

Build five things. Cut everything else without sentiment — you do not have time to be attached to features.

**Build:**
1. WhatsApp Sandbox (or Telegram) webhook agent as the single interface.
2. Text-to-ledger logging with an explicit approval state machine (log → confirm → post).
3. Simple burn-rate forecast (linear projection on a few months of seeded/real transactions) that outputs a dollar gap.
4. Gap-sized grant retrieval against live Grants.gov data (see §10 for the exact API calls) filtered to nonprofit eligibility codes.
5. Ledger-grounded draft generation with visible source provenance, ending in a YES-to-approve / EDIT-to-revise loop.

**Cut for this build (list as roadmap in the README, don't build):**
- Actual grant submission (legally/technically out of scope — see §7).
- Voice memo logging (Transcribe adds an async media pipeline for very little judge-visible payoff).
- Bank/Plaid reconciliation.
- Officer handoff mode, board PDF reports, win-likelihood scoring, warm-intro surfacing, rejection learning loop.
- Foundation/private grant data (Candid is paywalled at $219+/month; mention as a paid-tier roadmap item, don't fake it).
- 990-N e-filing.

**Add only if ahead of schedule on day 3:** Receipt photo capture via Amazon Textract's `AnalyzeExpense` — it's a single synchronous API call with no template setup, roughly 2 hours of work. Low differentiation value (every receipt-OCR hackathon project already does this) but cheap if you have slack.

## 9. Technical architecture (upgraded)

The original doc's architecture was a router plus two sub-agents — functional, but not distinctive on Technical Implementation. Use a real multi-agent graph instead; it's a better story and only marginally more work with Strands.

```
EventBridge Scheduler (background sweep, no human trigger)
        │
        ▼
┌───────────────────────────────────────────────────┐
│  Strands multi-agent graph, on AgentCore Runtime  │
│                                                     │
│  Forecaster → Scout → Eligibility Screener →      │
│  Drafter → Compliance Reviewer                     │
└───────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
  Ledger store (DynamoDB)          interrupt() → WhatsApp/Telegram
  balances, dues, history           "Reply YES to approve / EDIT"
```

| Agent | Job |
|---|---|
| **Forecaster** | Projects balance forward from logged transactions, outputs a dollar gap and a date it becomes real |
| **Scout** | Queries Grants.gov for opportunities whose award range brackets the gap |
| **Eligibility Screener** | Checks EIN, org age, budget size, and applicant type against each opportunity's stated criteria before anyone's time is spent drafting |
| **Drafter** | Writes the narrative and budget-justification sections using real ledger figures, with source provenance |
| **Compliance Reviewer** | Checks the draft against the opportunity's stated requirements before it reaches a human |

**Human-in-the-loop:** implement the YES/EDIT approval as a Strands `interrupt()` at the protocol level, not an if-statement in application code. This is a small extra step that meaningfully strengthens the "surfaces only when there's a real decision to make" story the hackathon theme explicitly asks for.

**Stack:**
| Layer | Choice |
|---|---|
| Input channel | Twilio WhatsApp Sandbox webhook, Telegram Bot API, or iMessage via Blooio (third-party relay) |
| Orchestration | Strands Agents SDK, multi-agent graph (`GraphBuilder`) |
| Runtime | Amazon Bedrock AgentCore Runtime — deploy for real, this scores points |
| Memory | AgentCore Memory (short-term + long-term) — donor names, past rejections, recurring expenses |
| Identity/Security | AgentCore Identity |
| Observability | AgentCore Observability / OpenTelemetry traces — put a live trace on screen in the demo video, your judges are AWS engineers |
| Grant data | Grants.gov `search2` + `fetchOpportunity` (see §10) |
| Receipt OCR (optional) | Amazon Textract `AnalyzeExpense` |

## 10. Grant data — confirmed working today, use this exact approach

Two free, keyless Grants.gov endpoints, both confirmed live on Sept 10, 2026:

- **`POST https://api.grants.gov/v1/api/search2`** — no auth required. Filter by `keyword`, `eligibilities`, `agencies`, `oppStatuses` (use `posted`), `fundingCategories`. Returns id, title, agency, open/close dates, status. **Has no award-amount filter.**
- **`POST https://api.grants.gov/v1/api/fetchOpportunity`** — no auth required. Pass an opportunity id from search2, get back `awardCeiling`, `awardFloor`, `estimatedFunding`, `numberOfAwards`, `applicantTypes` (includes "Nonprofits having a 501(c)(3) status"), full eligibility description.

**Build it as a two-stage pipeline:** `search2` for a nonprofit-relevant shortlist filtered by `oppStatuses=posted` and eligibility codes, then `fetchOpportunity` per candidate, then filter client-side on `awardFloor ≤ your gap ≤ awardCeiling`. Cache 200–300 results to a local file well before the demo — never depend on a live external call while presenting.

If time allows, there's also a newer `api.simpler.grants.gov` endpoint with native `award_floor`/`award_ceiling` filters, but it requires a self-service API key and returned a 401 without one in testing. Treat it as a nice-to-have upgrade, not the critical path — build on the keyless endpoints first.

Foundation/private grant data (Candid) is paywalled ($219+/month) — don't fake having it. State honestly in the demo: "federal opportunities shown are real and live; foundation data is a paid-tier roadmap item."

## 11. Competitive landscape (for the README's honesty section)

| Tool | What it does | Gap vs. Chest |
|---|---|---|
| Instrumentl | AI grant matching + writing + accounting-system connection | No gap-triggered (dollar-sized) matching; not chat-native |
| Grantable, Vee, Granted AI, Grant Assistant | AI grant discovery + drafting, various scales | Match on mission/profile, not on a live forecasted dollar gap |
| GrantFlow | Cash forecasting, funding-gap alerts | No grant discovery layer at all |
| Bonterra Que, Blackbaud Development Agent | Agentic nonprofit platforms | Enterprise-oriented, not chat-first, not priced for sub-$50K orgs |
| AlignMint (Minty) | Free nonprofit AI accounting via chat | Explicitly refuses to create/update/delete records — read-only by design |
| Sage/Fyle, MoneyFeed | SMS/WhatsApp-native expense logging | Not nonprofit-specific, no grant layer |

## 12. Ethics and compliance — state these proactively in the pitch

- **The agent never submits a grant application.** It drafts; a human approves and files. This is required by law (Grants.gov needs a human Authorized Organization Representative with SAM.gov registration) and by at least one major funder's explicit policy (NIH's NOT-OD-25-132 excludes applications substantially developed by AI, with post-award consequences for violations). Frame this as a trust feature, not a limitation you ran out of time to build.
- Every dollar figure in a draft should be traceable to a specific ledger entry — show this provenance in the UI/demo, it's a cheap trust signal.
- Be upfront in the video about which channel is live (WhatsApp/Telegram, and iMessage via the disclosed third-party relay Blooio) versus roadmap (SMS), and which data is live (Grants.gov federal) versus roadmap (paywalled foundation data).

## 13. Judging-criteria fit

- **Technological Implementation:** real 5-agent Strands graph, scheduled background execution on AgentCore, protocol-level human interrupt, live observability traces.
- **Design:** entire product surface is one chat thread — a complete, coherent experience, not a tech demo bolted onto a UI.
- **Potential Impact:** dollar-denominated, verifiable problem (§2) with a concrete mechanism that closes it.
- **Creativity & Originality:** the specific, narrow, defensible claim in §4 — not a blanket "nobody does this," which would fail.
- **Presentation:** one demo beat carries the whole pitch — a real shortfall, a real live grant sized to close it, drafted with real numbers, one approval tap.

## 14. Sources

Grants.gov API: https://www.grants.gov/api/api-guide · Candid grant-funding data: https://candid.org/ · Giving USA 2025 figures via Candid · Twilio A2P 10DLC blocking: https://www.twilio.com/docs/messaging/compliance/a2p-10dlc/quickstart · Twilio WhatsApp Sandbox: https://www.twilio.com/docs/whatsapp/sandbox · Apple Messages for Business (no public send API): https://register.apple.com/resources/messages/messaging-documentation/ · NIH AI-application policy: https://grants.nih.gov/grants/guide/notice-files/NOT-OD-25-132.html · Instrumentl: https://www.instrumentl.com/ · GrantFlow: https://grantflow.tech/ · AlignMint: https://www.getalignmint.org/docs/minty-ai-overview · Amazon Textract AnalyzeExpense: https://docs.aws.amazon.com/textract/latest/dg/invoices-receipts.html

Full research backing this file: `research/chest_prior_art.md` (130 sources) and `DECISION_MEMO_Chest_vs_Quorum.md` in the project workspace. Naming decision note: prior-art check flagged real conflicts (see §3) but team elected to keep "Chest" given the US-only hackathon launch.

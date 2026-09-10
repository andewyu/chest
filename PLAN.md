# Chest — four-day build plan

**Now:** Thursday, September 10, 2026
**Deadline:** Monday, September 14, 2026, **5:00 PM PT**

Four working days (Thu–Sun) with Monday morning as buffer. Everything below is
sequenced so that **you have a submittable project by the end of Day 2.** Days 3
and 4 make it win. If you fall behind, you cut from the bottom of each day, never
from the top.

**The rule for the whole week:** the demo is one beat — *a real shortfall, a real
live grant sized to close it, drafted with real numbers, one approval tap.* Every
hour either makes that beat land harder or it's cut.

---

## Day 0 — tonight, 60–90 minutes (Thu evening)

Accounts and access take wall-clock time you can't compress later. Do this
before you write a line of agent code.

- [ ] **AWS: enable Bedrock model access** in your target region (`us-west-2`).
      Console → Bedrock → Model access → request Claude Sonnet. Approval is
      usually instant but is not guaranteed — this is the single item most
      likely to silently block you tomorrow.
- [ ] **Verify AgentCore Runtime is available** in that region on your account.
      If it isn't, switch region tonight, not Saturday.
- [ ] **Telegram bot token** — message @BotFather, `/newbot`, save the token.
      Two minutes, no review. Do this *and* Twilio; Telegram is your safety net.
- [ ] **Twilio WhatsApp Sandbox** — console → Messaging → Try it out → WhatsApp.
      Join the sandbox from your phone. No sender registration.
      Do **not** attempt SMS/10DLC. It cannot clear before Monday.
- [ ] `git clone https://github.com/andewyu/chest && cd chest`
      `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
      `cp .env.example .env` and fill it in.
- [ ] `python -m scripts.seed_ledger` — you should see a gap around **$14,800**.
- [ ] `python -m scripts.cache_grants --gap 14849` — confirm the Grants.gov
      endpoints answer from your machine and that real opportunities bracket
      that gap. **If nothing brackets $14.8k, tune the seed ledger tonight**
      until the gap lands in a band where real federal money exists. Your entire
      demo depends on this number being matchable.
- [ ] Register for the hackathon and read the submission form fields end to end.
      Know what you'll be asked for before Sunday night.

**Stop when:** the cache has 200+ opportunities and at least three of them
bracket your seeded gap.

---

## Day 1 — Friday: the conversation works end to end

Goal by end of day: **you can text the bot and it logs money, confirms it, and
tells you your balance.** No graph yet. No grants yet.

### Morning (3–4h)
1. `uvicorn chest.channels.webhook:app --reload --port 8000` + `ngrok http 8000`.
2. Point Telegram at it: `curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<ngrok>/telegram"`.
   Point the Twilio sandbox at `<ngrok>/whatsapp`.
3. Get `TREASURER` (`chest/agents/treasurer.py`) responding over both. Fix the
   Strands `Agent(...)` call signature against whatever version actually
   installed — the scaffold is written to the documented API, verify it.
4. Prove the **log → confirm → post** state machine by hand:
   - "paid 47 dollars for hoses" → pending entry read back, asks to confirm
   - "yes" → posted, balance updates
   - "no" → discarded, balance unchanged

### Afternoon (3–4h)
5. Session state: right now `handle()` shares one agent across all chats. Give
   each `session_id` its own conversation so two testers don't collide.
6. Make replies *short*. Test on your actual phone, not a terminal. If a reply
   wraps past four lines on a phone screen, the prompt is wrong.
7. Wire `current_balance` and confirm "what's in the chest?" answers correctly.
8. **Commit and push.** Tag it `v0.1-conversation`.

### Evening (1h) — the thing everyone skips
9. Write the first 60 seconds of your demo script *now*, in `docs/demo.md`, as
   literal lines you will type into the phone. Writing it now tells you what's
   missing while you still have three days to build it.

**Cut first if behind:** WhatsApp. Ship Telegram only, mention WhatsApp parity in the README.

---

## Day 2 — Saturday: the gap-to-grant loop

Goal by end of day: **a real forecasted gap retrieves a real live grant and
produces a draft with cited numbers.** This is the whole product. If you get
here, you have a submission.

### Morning (4h)
1. `chest/tools/forecast.py` — sanity-check the projection against the seeded
   ledger. Does the gap number *feel* right to a human reading the ledger? If
   not, fix it now; every downstream claim rests on it.
2. `chest/tools/grants_gov.py` — run `match_gap()` against the real cache.
   Read the top five hits yourself. **Are they plausible for a community
   garden?** If they're absurd, add a keyword pre-filter before the bracket
   filter — the gap is the primary key, but it doesn't have to be the only one.
3. Build the graph in `chest/agents/graph.py` and run it once end to end with
   `python -m scripts.sweep --dry-run`. Expect to spend real time on the
   `GraphBuilder` API and on payload shapes between nodes.

### Afternoon (4h)
4. **Provenance is the differentiator — make it real.** Every dollar figure the
   Drafter emits must carry a ledger id. Add a hard post-check: regex the draft
   for `$` amounts, verify each is followed by a bracketed id that exists in the
   ledger, and have the Compliance Reviewer reject the draft if any aren't.
   A judge will test exactly this.
5. Make the final message phone-shaped: one line of summary, then the draft,
   then "Reply YES to approve, EDIT to revise."
6. Implement YES / EDIT handling. Get it working as plain state first — the
   protocol-level `interrupt()` upgrade is Day 3.
7. **Commit and push.** Tag `v0.2-gap-to-grant`. **You are now submittable.**

### Evening (1h)
8. Record a throwaway phone-screen capture of the full loop. Not for submission —
   for you, to see where it drags. It will drag somewhere. Note where.

**Cut first if behind:** the Compliance Reviewer node. Fold its check into the
Drafter's prompt and keep four agents. Say four, not five, in the README.

---

## Day 3 — Sunday: deploy, instrument, and make it look like an AWS project

Goal: **it runs on AWS, on a schedule, with traces you can put on screen.** The
judges are AWS engineers. A local-only demo scores badly on Technological
Implementation no matter how good the idea is.

### Morning (4h)
1. **Deploy to Bedrock AgentCore Runtime.** Budget the whole morning; deployment
   is always the step that eats a day. Get *something* deployed even if the
   local path stays your demo path.
2. **EventBridge Scheduler** → `scripts.sweep:lambda_handler` on a cron. Then
   prove the money shot: **you don't touch anything, and your phone buzzes with
   a shortfall and a matched grant.** That unprompted buzz is your demo's peak.
   Everything else is setup for it.
3. **AgentCore Observability / OTel.** Get a trace view showing the five nodes
   firing in sequence. Screenshot it. You will put this on screen in the video.

### Afternoon (3h)
4. Upgrade YES/EDIT to a real Strands `interrupt()`. Small change, direct hit on
   the "surfaces only when there's a real decision" judging line.
5. **AgentCore Memory:** persist donor names and recurring expenses across
   sessions. One visible payoff is enough — e.g. the agent recognizes "the
   Hensleys" on a second mention without being told again.
6. Switch the ledger to DynamoDB (`CHEST_STORE=dynamodb`). Seed it. Keep the
   local JSON path working as your demo fallback.

### Evening (2h)
7. **Freeze the feature set.** Whatever isn't working by tonight goes in the
   README roadmap, not into Monday.
8. `python -m scripts.cache_grants` fresh, commit the cache, and **never make a
   live external call during the recording.**
9. Only if genuinely ahead: Textract `AnalyzeExpense` receipt photos (~2h). It's
   low differentiation — every receipt-OCR project does it — so it's the first
   thing to skip.

**Cut first if behind:** DynamoDB and Memory. A deployed runtime + scheduled
sweep + a trace is the scoring core; the rest is polish.

---

## Day 4 — Monday: record, write, submit (target: done by 1 PM PT)

You have until 5 PM PT. Treat 1 PM as the deadline. Uploads fail, forms time
out, and you will find one bug while recording.

### 8–10 AM — the video (3 minutes, hard cap)
Structure, timed:

| Time | Beat |
|---|---|
| 0:00–0:20 | The problem, one stat: 60% of nonprofits, 0.4% of the money. |
| 0:20–0:40 | Phone screen. Text a transaction in. It confirms. That's the whole UI. |
| 0:40–1:20 | **The buzz.** Unprompted: "You're $14,849 short by Feb 1. I found a grant that brackets it." Do not touch the phone before it arrives. |
| 1:20–2:10 | Open the draft. Point at a dollar figure and its ledger id. Say: every number traces to a line in their books. |
| 2:10–2:30 | Say YES. Show it approve — and say out loud: **Chest never submits. A human files it.** |
| 2:30–2:50 | Cut to the AgentCore trace: five agents, scheduled, no human trigger. |
| 2:50–3:00 | The line: *"Chest doesn't just track your money. It goes and finds the money you're missing."* |

Say the constraints plainly on camera — WhatsApp vs. SMS registration, federal
data live vs. foundation data paywalled. **Judges respect disclosed constraints
and penalize discovered ones.** Twenty seconds of honesty buys you the rest.

### 10 AM–12 PM — the write-up
- Finish the README (the honesty section is already scaffolded — keep it).
- Architecture diagram as an image, not ASCII.
- Fill the submission form. Map your text directly onto the five judging
  criteria — don't make a judge infer the fit:
  - *Technological Implementation:* 5-agent Strands graph, AgentCore Runtime,
    scheduled background execution, protocol-level interrupt, live traces.
  - *Design:* the entire surface is one chat thread.
  - *Potential Impact:* $117.15B given; 60% of orgs get 0.4% of it.
  - *Creativity:* the gap-as-retrieval-key claim — narrow, and it survives a
    fact-check. Do **not** claim nobody connects budgets to grants.
  - *Presentation:* one beat, carried clean.

### 12–1 PM — submit
- Repo public ✅ (already is), README complete, video unlisted-but-viewable,
  **test the video link in a private window.**
- Submit. Then stop.

---

## The five things most likely to sink this

1. **Bedrock model access isn't enabled** and you find out Friday morning. → Day 0.
2. **Nothing real brackets your gap.** The retrieval story dies silently. → verify Day 0, tune the seed.
3. **AgentCore deployment eats Sunday and Monday.** → timebox it to Sunday morning; keep local as the demo path.
4. **A live API call fails on camera.** → cache everything Sunday night, no exceptions.
5. **Scope creep.** Voice memos, Plaid, PDF reports, win-scoring. Every one of them is in the README roadmap for a reason. Build five things.

## Non-negotiables

- The agent **never submits** an application. Say it out loud in the video.
- Every dollar figure in a draft cites a ledger entry.
- Don't reintroduce the $104B figure or the $4–7B matching-gifts stat.
- Don't claim iMessage or SMS as shipped.
- Don't claim "no tool connects budget monitoring to grant discovery."

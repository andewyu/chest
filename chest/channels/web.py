"""The signup surface: where an org gets its own books.

Deliberately small. Three pages — sign up, here's your code, here's your money
— because the product is the text thread, and this is the doorway to it.

The dashboard URL contains the account id and nothing else, which makes it a
capability link: whoever has it can read that org's books. That's the right
tradeoff for a demo and the wrong one for real donor money, so it says so on
the page rather than implying a login exists.
"""
from __future__ import annotations

import html

from chest.config import PUBLIC_URL

STYLE = """
:root { color-scheme: light dark; --ink:#14110f; --paper:#faf7f2; --line:#e3ddd2;
        --muted:#6b6259; --accent:#1f6f4a; --bad:#a33a2a; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#f2efe9; --paper:#16130f; --line:#332c24; --muted:#a89c8d; --accent:#5fbf8f; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--paper); color:var(--ink); font:16px/1.55 ui-sans-serif,
       -apple-system, "Segoe UI", system-ui, sans-serif; }
.wrap { max-width: 44rem; margin: 0 auto; padding: 3rem 1.25rem 5rem; }
h1 { font-size: 1.9rem; letter-spacing:-.02em; margin:0 0 .35rem; }
h2 { font-size: 1.05rem; margin: 2.5rem 0 .75rem; letter-spacing:.02em;
     text-transform: uppercase; color: var(--muted); }
p.sub { color: var(--muted); margin:0 0 2rem; }
label { display:block; font-size:.85rem; color:var(--muted); margin:1rem 0 .3rem; }
input, select { width:100%; padding:.6rem .7rem; font:inherit; color:inherit;
        background:transparent; border:1px solid var(--line); border-radius:8px; }
button { margin-top:1.6rem; padding:.7rem 1.2rem; font:inherit; font-weight:600;
         color:var(--paper); background:var(--accent); border:0; border-radius:8px;
         cursor:pointer; }
.row { display:flex; gap:1rem; } .row > * { flex:1; }
.card { border:1px solid var(--line); border-radius:12px; padding:1.25rem 1.4rem; margin:1rem 0; }
.code { font:600 2rem/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
        letter-spacing:.28em; color:var(--accent); }
.big { font:600 2rem/1.2 ui-sans-serif, system-ui, sans-serif; letter-spacing:-.02em; }
table { width:100%; border-collapse:collapse; font-size:.94rem; }
td { padding:.5rem 0; border-bottom:1px solid var(--line); vertical-align:top; }
td.amt { text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
td.out { color:var(--bad); } td.in { color:var(--accent); }
.muted { color:var(--muted); } .small { font-size:.85rem; }
a { color:var(--accent); }
ol { padding-left:1.1rem; } ol li { margin:.4rem 0; }
.warn { border-left:3px solid var(--muted); padding-left:.9rem; }
"""


def page(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{STYLE}</style></head>"
        f"<body><div class='wrap'>{body}</div></body></html>"
    )


APPLICANT_TYPES = [
    "Nonprofits having a 501(c)(3) status other than institutions of higher education",
    "Nonprofits without 501(c)(3) status other than institutions of higher education",
    "Public and State controlled institutions of higher education",
    "Private institutions of higher education",
    "Small businesses",
    "Native American tribal organizations",
]

STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY","DC",
]


def signup_form(error: str = "") -> str:
    types = "".join(f"<option value='{html.escape(t)}'>{html.escape(t)}</option>" for t in APPLICANT_TYPES)
    states = "".join(f"<option{' selected' if s == 'IN' else ''}>{s}</option>" for s in STATES)
    banner = f"<div class='card' style='border-color:var(--bad)'>{html.escape(error)}</div>" if error else ""
    return page(
        "Chest — sign up",
        f"""
        <h1>Chest</h1>
        <p class='sub'>A treasurer for volunteer-run nonprofits that lives in a text
        thread. Log what you spend, ask what's left, and find out about a shortfall
        before it happens.</p>
        {banner}
        <form method='post' action='/signup'>
          <label for='name'>Organization name</label>
          <input id='name' name='name' required placeholder='Riverside Community Garden Collective'>
          <div class='row'>
            <div>
              <label for='ein'>EIN</label>
              <input id='ein' name='ein' placeholder='00-0000000'>
            </div>
            <div>
              <label for='state'>State</label>
              <select id='state' name='state'>{states}</select>
            </div>
          </div>
          <label for='applicant_type'>Applicant type (used for grant eligibility)</label>
          <select id='applicant_type' name='applicant_type'>{types}</select>
          <label for='annual_budget'>Annual budget (USD)</label>
          <input id='annual_budget' name='annual_budget' inputmode='numeric' value='42000'>
          <label class='small'>
            <input type='checkbox' name='seed' value='1' style='width:auto'>
            Start with a sample year of books, so there's something to ask about
          </label>
          <button type='submit'>Create our books</button>
        </form>
        <h2>What happens next</h2>
        <ol class='muted small'>
          <li>You get an 8-character code.</li>
          <li>Text it to the bot. That links your phone to your organization.</li>
          <li>Everything after that is just texting: "paid 47 for hoses", "what's left".</li>
        </ol>
        """,
    )


def linked_page(account, bot_username: str, seeded: bool) -> str:
    bot = f"@{html.escape(bot_username)}" if bot_username else "the Chest bot"
    open_link = (
        f"<p><a href='https://t.me/{html.escape(bot_username)}'>Open {bot} in Telegram</a></p>"
        if bot_username else ""
    )
    seed_note = (
        "<p class='muted small'>We've loaded a sample year of books so you have "
        "something to ask about. Try \"what's the balance\".</p>" if seeded else ""
    )
    return page(
        f"Chest — {account.name}",
        f"""
        <h1>{html.escape(account.name)} is set up.</h1>
        <p class='sub'>One step left: link your phone.</p>
        <div class='card'>
          <div class='muted small'>Text this code to {bot}</div>
          <div class='code'>{html.escape(account.link_code)}</div>
        </div>
        {open_link}
        {seed_note}
        <h2>Your books</h2>
        <p><a href='{PUBLIC_URL}/a/{account.id}'>{PUBLIC_URL}/a/{account.id}</a></p>
        <p class='warn muted small'>Anyone with that link, or that code, can read and
        add to these books. There are no passwords here yet — it's a demo. Don't put
        real donor data in it.</p>
        """,
    )


def dashboard(account, balance_display, gap, entries, identities, runs_out_on="") -> str:
    rows = "".join(
        f"<tr><td class='muted small'>{html.escape(e['date'])}</td>"
        f"<td>{html.escape(e['memo'])}<div class='muted small'>{html.escape(e['kind'])}</div></td>"
        f"<td class='amt {e['direction']}'>{'−' if e['direction'] == 'out' else '+'}"
        f"{html.escape(e['amount_display'])}</td></tr>"
        for e in entries
    ) or "<tr><td class='muted'>Nothing posted yet. Text the bot to log something.</td></tr>"

    if gap.is_real:
        outlook = (
            f"<div class='card'><div class='muted small'>Outlook</div>"
            f"<div>Short <b>${gap.amount:,.2f}</b> by "
            f"{html.escape(runs_out_on or gap.goes_negative_on or '')}, at "
            f"${abs(gap.monthly_net):,.2f}/mo out.</div></div>"
        )
    else:
        outlook = (
            f"<div class='card'><div class='muted small'>Outlook</div>"
            f"<div>No shortfall in the next {gap.horizon_days} days.</div></div>"
        )

    linked = "".join(f"<li>{html.escape(i.key)}</li>" for i in identities) or "<li class='muted'>nothing linked yet</li>"

    return page(
        f"Chest — {account.name}",
        f"""
        <h1>{html.escape(account.name)}</h1>
        <p class='sub muted small'>{html.escape(account.applicant_type)} · {html.escape(account.state)}
        · budget ${account.annual_budget:,.0f}</p>
        <div class='card'>
          <div class='muted small'>Balance</div>
          <div class='big'>{html.escape(balance_display)}</div>
        </div>
        {outlook}
        <h2>Recent entries</h2>
        <table>{rows}</table>
        <h2>Linked devices</h2>
        <ul class='small'>{linked}</ul>
        <h2>Link code</h2>
        <div class='card'><div class='code'>{html.escape(account.link_code)}</div></div>
        <p class='warn muted small'>Capability link: anyone with this URL or code can
        read and add to these books. Demo only.</p>
        """,
    )

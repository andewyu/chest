"""Grants.gov client — two keyless endpoints, confirmed live.

    POST https://api.grants.gov/v1/api/search2          -> shortlist (no award filter)
    POST https://api.grants.gov/v1/api/fetchOpportunity -> awardFloor / awardCeiling

search2 has NO award-amount filter, which is exactly the thing Chest needs to
filter on. So this is a two-stage pipeline: shortlist by eligibility + status,
hydrate each candidate, then filter client-side on

    awardFloor <= gap <= awardCeiling

Cache before you demo. Never make a live external call while presenting.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

import httpx

from chest.config import GRANTS_CACHE

BASE = "https://api.grants.gov/v1/api"

# Grants.gov eligibility codes for nonprofits.
#   12 = Nonprofits with 501(c)(3) status (other than IHEs)
#   13 = Nonprofits WITHOUT 501(c)(3) status (other than IHEs)
#   25 = Others (see text field for details)
NONPROFIT_ELIGIBILITY = ["12", "13", "25"]


@dataclass
class Opportunity:
    id: str
    number: str
    title: str
    agency: str
    close_date: str | None
    award_floor: float | None
    award_ceiling: float | None
    estimated_funding: float | None
    number_of_awards: int | None
    applicant_types: list[str]
    description: str
    url: str

    def brackets(self, gap: float) -> bool:
        """True if this opportunity's award range contains the forecasted gap."""
        floor = self.award_floor if self.award_floor not in (None, 0) else 0.0
        ceiling = self.award_ceiling if self.award_ceiling not in (None, 0) else None
        if ceiling is None:
            return gap >= floor
        return floor <= gap <= ceiling


def search(
    keyword: str = "",
    rows: int = 100,
    eligibilities: list[str] | None = None,
    funding_categories: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Stage 1: shortlist currently-posted opportunities."""
    payload = {
        "keyword": keyword,
        "oppStatuses": "posted",
        "rows": rows,
        "eligibilities": "|".join(eligibilities or NONPROFIT_ELIGIBILITY),
    }
    if funding_categories:
        payload["fundingCategories"] = "|".join(funding_categories)

    r = httpx.post(f"{BASE}/search2", json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("data", {}).get("oppHits", [])


def fetch(opportunity_id: str | int) -> Opportunity | None:
    """Stage 2: hydrate one opportunity so we can read its award range."""
    r = httpx.post(
        f"{BASE}/fetchOpportunity", json={"opportunityId": int(opportunity_id)}, timeout=30
    )
    r.raise_for_status()
    d = r.json().get("data") or {}
    synopsis = d.get("synopsis") or {}
    if not synopsis:
        return None

    return Opportunity(
        id=str(d.get("id", opportunity_id)),
        number=d.get("opportunityNumber", ""),
        title=d.get("opportunityTitle", ""),
        agency=synopsis.get("agencyName") or d.get("agencyName", ""),
        close_date=synopsis.get("responseDate"),
        award_floor=_num(synopsis.get("awardFloor")),
        award_ceiling=_num(synopsis.get("awardCeiling")),
        estimated_funding=_num(synopsis.get("estimatedFunding")),
        number_of_awards=int(synopsis.get("numberOfAwards") or 0) or None,
        applicant_types=[
            a.get("description", "") for a in (synopsis.get("applicantTypes") or [])
        ],
        description=_strip(synopsis.get("synopsisDesc", "")),
        url=f"https://www.grants.gov/search-results-detail/{d.get('id', opportunity_id)}",
    )


def match_gap(gap: float, cache: list[Opportunity] | None = None) -> list[Opportunity]:
    """The core retrieval step: the dollar gap IS the query."""
    pool = cache if cache is not None else load_cache()
    hits = [o for o in pool if o.brackets(gap)]
    # Tightest bracket first — an award range snug around the gap is the best fit.
    hits.sort(key=lambda o: (o.award_ceiling or 1e12) - (o.award_floor or 0))
    return hits


# ---------- cache ----------

def save_cache(opps: list[Opportunity]) -> None:
    GRANTS_CACHE.write_text(json.dumps([asdict(o) for o in opps], indent=2))


def load_cache() -> list[Opportunity]:
    if not GRANTS_CACHE.exists():
        return []
    return [Opportunity(**o) for o in json.loads(GRANTS_CACHE.read_text())]


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def _strip(html: str) -> str:
    import re

    return re.sub(r"<[^>]+>", " ", html or "").replace("&nbsp;", " ").strip()

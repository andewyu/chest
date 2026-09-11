"""Cache live Grants.gov opportunities to disk before the demo.

Never make a live external call while presenting. Run this the morning of.

    python -m scripts.cache_grants
    python -m scripts.cache_grants --gap 12500   # also show what would match
"""
from __future__ import annotations

import argparse
import time

from chest.tools import grants_gov as gg

KEYWORDS = [
    "museum", "local history", "heritage preservation", "historic preservation",
    "museum education", "collections care", "cultural heritage", "public history",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=40, help="rows per keyword")
    ap.add_argument("--gap", type=float, default=None)
    args = ap.parse_args()
    if args.rows < 1:
        ap.error("--rows must be at least 1")

    seen: dict[str, dict] = {}
    for kw in KEYWORDS:
        try:
            for hit in gg.search(keyword=kw, rows=args.rows):
                seen[str(hit["id"])] = hit
            print(f"  {kw:<20} running total {len(seen)}")
        except Exception as exc:
            print(f"  {kw:<20} FAILED: {exc}")
        time.sleep(0.3)

    print(f"\nHydrating {len(seen)} opportunities (this is the slow part)...")
    opps = []
    for i, opp_id in enumerate(seen, 1):
        try:
            o = gg.fetch(opp_id)
            if o:
                opps.append(o)
        except Exception as exc:
            print(f"  [{i}] {opp_id} failed: {exc}")
        if i % 25 == 0:
            print(f"  {i}/{len(seen)}")
        time.sleep(0.2)

    gg.save_cache(opps)
    with_range = [o for o in opps if o.award_ceiling]
    print(f"\nCached {len(opps)} opportunities ({len(with_range)} with an award range).")

    if args.gap:
        hits = gg.match_gap(args.gap, opps)
        print(f"\n{len(hits)} bracket a ${args.gap:,.0f} gap:")
        for o in hits[:10]:
            print(f"  ${o.award_floor or 0:>10,.0f}–${o.award_ceiling or 0:<12,.0f} "
                  f"{o.title[:64]}  ({o.agency})")


if __name__ == "__main__":
    main()

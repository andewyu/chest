# Grants.gov demo snapshot

`grants_cache.json` was refreshed from the public Grants.gov `search2` and
`fetchOpportunity` endpoints on September 10, 2026 (America/Indiana/Indianapolis).
It contains 112 real posted opportunities discovered with museum and heritage
mission terms. Seven records both match those terms and bracket the seeded
$14,849 funding gap.

The strongest seeded-demo candidate is **Inspire Grants for Small Museums
(2027)** from the Institute of Museum and Library Services, Grants.gov
opportunity `363771`. Its published award range is $5,000–$75,000 and its
published close date is November 13, 2026.

Refresh before recording or presenting:

```bash
python -m scripts.cache_grants --gap 14849
```

The cache is public grant data and contains no credentials. Account records,
per-organization ledgers, session snapshots, and draft approval state remain
ignored because they contain organization-specific information or link codes.

from datetime import date

from chest.tools.forecast import forecast
from chest.store.ledger import LedgerStore
from scripts.seed_ledger import build


def test_seeded_ledger_produces_a_real_gap():
    store = LedgerStore()
    store._replace_all(build())
    gap = forecast(store=store)
    assert gap.is_real, gap.summary()
    assert gap.amount > 0
    assert gap.goes_negative_on is not None
    assert gap.evidence, "a gap with no ledger citations is not usable in a draft"


def test_gap_brackets_are_inclusive():
    from chest.tools.grants_gov import Opportunity

    o = Opportunity(
        id="1", number="X", title="t", agency="a", close_date=None,
        award_floor=10000, award_ceiling=25000, estimated_funding=None,
        number_of_awards=None, applicant_types=[], description="", url="",
    )
    assert o.brackets(10000)
    assert o.brackets(25000)
    assert o.brackets(17500)
    assert not o.brackets(9999)
    assert not o.brackets(25001)


def test_open_ended_ceiling_matches_anything_above_floor():
    from chest.tools.grants_gov import Opportunity

    o = Opportunity(
        id="2", number="X", title="t", agency="a", close_date=None,
        award_floor=5000, award_ceiling=None, estimated_funding=None,
        number_of_awards=None, applicant_types=[], description="", url="",
    )
    assert o.brackets(500000)
    assert not o.brackets(100)

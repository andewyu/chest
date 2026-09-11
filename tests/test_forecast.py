from datetime import date

import pytest
from chest.tools.forecast import forecast
from chest.store.ledger import LedgerStore
from scripts.seed_ledger import build


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A ledger of its own, in a directory of its own. Never the real books."""
    monkeypatch.setattr("chest.store.ledger.LEDGERS_DIR", tmp_path)
    return LedgerStore("acct_test")


def test_seeded_ledger_produces_a_real_gap(store):
    store._replace_all(build())
    gap = forecast(store)
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


def test_missing_award_range_does_not_match_every_gap():
    from chest.tools.grants_gov import Opportunity

    o = Opportunity(
        id="3", number="X", title="t", agency="a", close_date=None,
        award_floor=None, award_ceiling=None, estimated_funding=None,
        number_of_awards=None, applicant_types=[], description="", url="",
    )

    assert not o.brackets(14849)


def test_gap_matching_requires_mission_relevance_before_range_tightness():
    from chest.tools.grants_gov import Opportunity, match_gap

    def opportunity(id, title, floor, ceiling):
        return Opportunity(
            id=id, number="X", title=title, agency="a", close_date=None,
            award_floor=floor, award_ceiling=ceiling, estimated_funding=None,
            number_of_awards=None, applicant_types=[], description="", url="",
        )

    irrelevant = opportunity("1", "Overseas diplomatic exchange", 14000, 15000)
    relevant = opportunity("2", "Inspire grants for small museums", 5000, 75000)

    assert match_gap(14849, [irrelevant, relevant], ["museum"]) == [relevant]

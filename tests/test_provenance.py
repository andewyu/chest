from chest.tools.provenance import validate_draft


def test_accepts_dollar_figures_with_real_ledger_citations():
    report = validate_draft(
        "We spent $1,240.00 [a3f19c2b1234] on supplies.",
        valid_entry_ids={"a3f19c2b1234"},
    )

    assert report.valid
    assert report.violations == []


def test_rejects_an_uncited_dollar_figure():
    report = validate_draft(
        "We are requesting $14,849 to close the gap.",
        valid_entry_ids={"a3f19c2b1234"},
    )

    assert not report.valid
    assert report.violations == ["$14,849 has no ledger citation"]


def test_rejects_a_citation_that_is_not_in_the_ledger():
    report = validate_draft(
        "We spent $640 [ffffffffffff] on testing.",
        valid_entry_ids={"a3f19c2b1234"},
    )

    assert not report.valid
    assert report.violations == ["$640 cites unknown ledger entry [ffffffffffff]"]

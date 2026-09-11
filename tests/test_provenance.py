from chest.tools.provenance import enforce_provenance, validate_draft


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


def test_hard_gate_blocks_an_uncited_generated_output():
    result = enforce_provenance(
        "Ready to request $14,849.", valid_entry_ids={"a3f19c2b1234"}
    )

    assert result.startswith("BLOCKED:")
    assert "$14,849 has no ledger citation" in result


def test_hard_gate_preserves_a_grounded_generated_output():
    draft = "Supplies cost $640 [a3f19c2b1234]."

    assert enforce_provenance(draft, {"a3f19c2b1234"}) == draft

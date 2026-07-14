"""Contract tests for data-integrity-check.sh (hard-logic only).

The script emits a human-readable report (no --json), so the contract matches
stable text markers. Only the two HARD structural checks are asserted:
referential integrity (orphan FK) and type consistency (mixed scalar types).
"""

import re

import pytest

import kit


@pytest.fixture(scope="session")
def report(seeded_db):
    res = kit.run_script("data-integrity-check.sh", "--db", seeded_db)
    assert res.returncode == 0, f"script failed (rc={res.returncode})\n{res.stderr}"
    return res.stdout + res.stderr


def _total(report_text, label):
    m = re.search(rf"Total {re.escape(label)}:\s*(\d+)", report_text)
    return int(m.group(1)) if m else None


@pytest.mark.integrity
def test_orphan_fk_detected(report, expected):
    assert "ORPHAN FK" in report, "expected an ORPHAN FK marker in the report"
    n = _total(report, "referential integrity issues")
    assert n is not None and n >= expected["min_referential_issues"], (
        f"referential integrity issues = {n}, expected >= "
        f"{expected['min_referential_issues']}"
    )


@pytest.mark.integrity
def test_orphan_points_at_customers(report):
    assert re.search(r"ORPHAN FK:\s*orders\.customer_id\s*(->|→)", report), \
        "expected orders.customer_id orphan against customers"


@pytest.mark.integrity
def test_type_inconsistency_detected(report, expected):
    field = expected["type_inconsistency"]["field"]
    assert "mixed types" in report, "expected a 'mixed types' marker in the report"
    assert re.search(rf'"{re.escape(field)}"\s+has mixed types', report), (
        f"expected field '{field}' to be flagged with mixed types"
    )
    n = _total(report, "type-consistency issues")
    assert n is not None and n >= 1, f"type-consistency issues = {n}, expected >= 1"


@pytest.mark.integrity
def test_no_soft_checks_present(report):
    """The hard-only checker must not emit the removed semantic checks."""
    for banned in ("Duplicate Detection", "Data Quality",
                   "Cross-Collection Orphan", "negative values", "outside 1-5"):
        assert banned not in report, f"removed soft check still present: {banned!r}"

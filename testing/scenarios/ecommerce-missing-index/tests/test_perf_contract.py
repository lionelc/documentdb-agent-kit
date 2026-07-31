"""Contract tests for perf-advisor.sh COLLSCAN detection.

perf-advisor.sh emits a human-readable report; the contract matches the stable
COLLSCAN markers and the "COLLSCAN total: N" counter.
"""

import re

import pytest

import kit


@pytest.fixture(scope="session")
def report(seeded_db):
    res = kit.run_script("perf-advisor.sh", "--db", seeded_db)
    assert res.returncode == 0, f"script failed (rc={res.returncode})\n{res.stderr}"
    return res.stdout + res.stderr


@pytest.mark.perf
def test_collscan_reported(report, expected):
    assert "COLLSCAN" in report, "expected at least one COLLSCAN marker"
    m = re.search(r"COLLSCAN total:\s*(\d+)", report)
    assert m is not None, "expected a 'COLLSCAN total: N' summary line"
    assert int(m.group(1)) >= expected["min_collscan_patterns"], (
        f"COLLSCAN total = {m.group(1)}, expected >= {expected['min_collscan_patterns']}"
    )


@pytest.mark.perf
def test_unindexed_collection_flagged(report, expected):
    coll = expected["unindexed_collection"]
    assert re.search(rf"COLLSCAN:\s*{re.escape(coll)}\b", report), (
        f"expected a COLLSCAN against the unindexed '{coll}' collection"
    )

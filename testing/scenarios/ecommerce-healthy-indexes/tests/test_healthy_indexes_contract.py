"""False-positive guard: a healthy DB must yield no redundancy findings."""

import pytest

import kit


@pytest.fixture(scope="session")
def findings(seeded_db):
    res = kit.run_script("index-redundancy-finder.sh", "--db", seeded_db, "--json",
                         want_json=True)
    assert res.returncode == 0, f"script failed (rc={res.returncode})\n{res.stderr}"
    assert res.json is not None, f"output was not valid JSON:\n{res.stdout[:500]}"
    return res.json


@pytest.mark.healthy_indexes
def test_no_structural_false_positives(findings, expected):
    structural = set(expected["structural_rules"])
    bad = [f"{f['collection']}.{f['index']} [{f['rule']}]"
           for f in findings if f["rule"] in structural]
    assert len(bad) <= expected["max_structural_findings"], (
        "structural false positives on a healthy DB: " + ", ".join(bad)
    )


@pytest.mark.healthy_indexes
def test_healthy_db_has_no_findings(findings, expected):
    assert len(findings) <= expected["max_total_findings"], (
        f"expected <= {expected['max_total_findings']} findings on a healthy DB, "
        f"got {len(findings)}:\n"
        + "\n".join(f"{f['collection']}.{f['index']} [{f['rule']}]" for f in findings)
    )

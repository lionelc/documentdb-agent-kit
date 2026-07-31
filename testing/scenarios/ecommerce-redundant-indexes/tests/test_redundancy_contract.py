"""Contract tests for index-redundancy-finder.sh against a fixture with
intentionally redundant indexes."""

import pytest

import kit


@pytest.fixture(scope="session")
def findings(seeded_db):
    """Run the redundancy finder once and reuse the parsed JSON across tests."""
    res = kit.run_script("index-redundancy-finder.sh", "--db", seeded_db, "--json",
                         want_json=True)
    assert res.returncode == 0, f"script failed (rc={res.returncode})\n{res.stderr}"
    assert res.json is not None, f"output was not valid JSON:\n{res.stdout[:500]}"
    return res.json


@pytest.mark.redundancy
def test_output_is_a_list(findings):
    assert isinstance(findings, list)


@pytest.mark.redundancy
def test_minimum_findings(findings, expected):
    assert len(findings) >= expected["min_total_findings"], (
        f"expected >= {expected['min_total_findings']} findings, got {len(findings)}"
    )


@pytest.mark.redundancy
def test_all_expected_detected(findings, expected):
    """Every entry in must_detect must be present.

    An entry matches on collection + (exact rule or any-of rule_any) and,
    optionally, a specific index name.
    """
    missing = []
    for exp in expected["must_detect"]:
        coll = exp["collection"]
        rules = [exp["rule"]] if "rule" in exp else list(exp["rule_any"])
        idx = exp.get("index")

        def matches(f):
            if f["collection"] != coll or f["rule"] not in rules:
                return False
            return idx is None or f["index"] == idx

        if not any(matches(f) for f in findings):
            label = f"{coll}.{idx or '*'} [{'|'.join(rules)}]"
            missing.append(label)
    assert not missing, (
        "missing expected findings: " + ", ".join(missing)
        + "\n--- actual findings ---\n"
        + "\n".join(f"{f['collection']}.{f['index']} [{f['rule']}]" for f in findings)
    )


@pytest.mark.redundancy
def test_keep_indexes_not_structurally_flagged(findings, expected):
    """KEEP indexes must never be reported with a structural redundancy rule."""
    structural = set(expected["structural_rules"])
    violations = []
    for keep in expected["must_not_flag_structural"]:
        for f in findings:
            if (f["collection"] == keep["collection"]
                    and f["index"] == keep["index"]
                    and f["rule"] in structural):
                violations.append(f"{f['collection']}.{f['index']} [{f['rule']}]")
    assert not violations, "KEEP indexes wrongly flagged: " + ", ".join(violations)

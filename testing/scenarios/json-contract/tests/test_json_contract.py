"""Shape guard for every diagnostic script's --json output.

Dataset-agnostic: asserts JSON validity + top-level/nested structure and that
--json stdout is pure JSON. Never asserts specific finding counts. The per-script
contract is read from expected-findings.yaml so it stays data-driven.
"""

from pathlib import Path

import pytest
import yaml

import kit

# Load the shape contract at collection time so we can parametrize over scripts.
_SPEC = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "expected-findings.yaml").read_text()
)
SHAPE = _SPEC["shape"]
TYPEMAP = {"list": list, "object": dict}


@pytest.fixture(scope="session")
def json_outputs(seeded_db):
    """Run every script once with --json; return {script: ScriptResult}."""
    out = {}
    for script in SHAPE:
        out[script] = kit.run_script(script, "--db", seeded_db, "--json",
                                     want_json=True)
    return out


@pytest.mark.jsoncontract
@pytest.mark.parametrize("script", list(SHAPE))
def test_emits_valid_json_of_expected_shape(json_outputs, script):
    res = json_outputs[script]
    assert res.returncode == 0, (
        f"{script} --json failed (rc={res.returncode})\n{res.stderr[:400]}"
    )
    assert res.json is not None, (
        f"{script} --json did not emit parseable JSON:\n{res.stdout[:400]}"
    )
    exp = SHAPE[script]
    want = TYPEMAP[exp["type"]]
    assert isinstance(res.json, want), (
        f"{script}: expected top-level {exp['type']}, got {type(res.json).__name__}"
    )
    for key in exp.get("keys", []):
        assert key in res.json, f"{script}: missing required top-level key '{key}'"


@pytest.mark.jsoncontract
def test_json_stdout_is_pure_json(json_outputs):
    """--json stdout must be ONLY JSON — no box headers, no psql SET tags."""
    for script, res in json_outputs.items():
        s = res.stdout.strip()
        assert s and s[0] in "{[", f"{script}: stdout is not JSON: {s[:80]!r}"
        for leak in ("╔", "═", "LAYER", "\nSET", "CHECK "):
            assert leak not in res.stdout, (
                f"{script}: non-JSON leakage {leak!r} in --json stdout"
            )


@pytest.mark.jsoncontract
def test_perf_advisor_nested_shape(json_outputs):
    d = json_outputs["perf-advisor.sh"].json
    assert isinstance(d["mongo"], list) and d["mongo"], "perf: mongo[] is empty"
    m = d["mongo"][0]
    for key in ("collections", "index_health", "collscans", "slow_queries", "summary"):
        assert key in m, f"perf mongo[0] missing '{key}'"
    assert isinstance(d["pg"], dict), "perf: pg is not an object"
    for key in ("config", "cache_top", "scan_mix", "unused_pg_indexes", "blocked_queries"):
        assert key in d["pg"], f"perf pg missing '{key}'"


@pytest.mark.jsoncontract
def test_data_integrity_nested_shape(json_outputs):
    d = json_outputs["data-integrity-check.sh"].json
    for side in ("referential_integrity", "type_consistency"):
        assert "issues" in d[side], f"integrity {side} missing 'issues'"
        assert "findings" in d[side], f"integrity {side} missing 'findings'"
        assert isinstance(d[side]["findings"], list)
    assert isinstance(d["ok"], bool), "integrity 'ok' must be a boolean"
    assert isinstance(d["total_issues"], int), "integrity 'total_issues' must be an int"

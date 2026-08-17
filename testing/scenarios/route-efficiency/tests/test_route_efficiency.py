"""Guards for the route-efficiency benchmark (text skills vs diagnostic scripts).

This benchmark replaces `token-tests/`, which compared payload BYTES with no
model and no correctness check. The properties below are what make the
replacement trustworthy; each is cheap, needs no infrastructure, and runs on
every PR.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

import kit

pytestmark = pytest.mark.routeefficiency

BENCH = kit.REPO_DIR / "benchmarks" / "documentdb-route-efficiency"
TASK = BENCH / "tasks" / "index-redundancy-diagnosis"
sys.path.insert(0, str(BENCH / "shared" / "verifier"))
import check_parity  # noqa: E402


@pytest.fixture(scope="module")
def expected():
    return yaml.safe_load((TASK / "expected-findings.yaml").read_text())


# ---------------------------------------------------------------------------
# arm design
# ---------------------------------------------------------------------------
def test_arms_are_mutually_exclusive_and_asserted():
    """A leftover file turns one arm into the other, and the run would still
    complete and still report a number — a confident comparison of an arm
    against itself. The installer must verify, not just copy."""
    script = (BENCH / "shared" / "arms" / "install-arm.sh").read_text()
    assert "route-text" in script and "route-script" in script
    assert "rm -rf" in script, "the installer must clear the previous arm"
    assert script.count("FATAL") >= 3, (
        "the installer must fail loudly when an arm is contaminated or empty"
    )
    assert "exit 1" in script


def test_instruction_does_not_reveal_the_route():
    """Both arms get the identical prompt. Naming a script or a skill would
    steer one arm and turn the comparison into instruction-following."""
    text = (TASK / "instruction.md").read_text().lower()
    for leak in ("kb-route", "script", "skill", "toolbox", "advisor", "finder"):
        assert leak not in text, f"instruction leaks the route: {leak!r}"


def test_harness_refuses_to_fabricate_runs():
    """Without an agent the harness must stop, not emit plausible numbers.

    A silent fallback here would produce something that looks like a
    measurement and is not — worse than producing nothing.
    """
    script = (BENCH / "run-comparison.sh").read_text()
    assert "AGENT_CMD is not set" in script
    assert "exit 2" in script


def test_harness_resets_every_shared_surface():
    """Each of these is a leak that would favour whichever arm ran second."""
    script = (BENCH / "run-comparison.sh").read_text()
    assert "drop_db" in script, "each run needs its own database"
    assert "ANALYZE" in script, "planner statistics must be settled after seeding"
    assert "arm_order" in script, "arm order must be randomised across iterations"
    assert 'rm -rf "$run_out"' in script, "a stale finding.json must not be graded"


def test_fixture_is_deterministic():
    """Both arms must see byte-identical data, or a cost difference could be a
    data difference."""
    # Strip comments first: the fixture's own docstring says "no Math.random()",
    # and matching that would be a false positive — the check must look at code.
    src = (TASK / "fixture.js").read_text()
    code = "\n".join(line.split("//")[0] for line in src.splitlines())
    assert "Math.random" not in code, (
        "fixture uses Math.random(); both arms must see byte-identical data or "
        "a cost difference could be a data difference"
    )


# ---------------------------------------------------------------------------
# parity grading — the gate on every cost number
# ---------------------------------------------------------------------------
def test_parity_accepts_the_correct_finding(expected):
    r = check_parity.grade(
        {"redundant_indexes": ["tenant_id_1", "email_1"],
         "reason": "tenant_id_1 is a prefix of the compound index; "
                   "email_1 duplicates email_unique"},
        expected)
    assert r["parity"] is True, r


def test_parity_rejects_a_missed_finding(expected):
    r = check_parity.grade(
        {"redundant_indexes": ["tenant_id_1"], "reason": "prefix"}, expected)
    assert r["parity"] is False and r["missed"] == ["email_1"]


def test_parity_rejects_naming_a_healthy_index(expected):
    """Over-reporting is not correctness."""
    r = check_parity.grade(
        {"redundant_indexes": ["tenant_id_1", "email_1", "email_unique"],
         "reason": "prefix and duplicate"}, expected)
    assert r["parity"] is False and "email_unique" in r["false_positives"]


def test_parity_rejects_listing_every_index(expected):
    """The obvious attack: an arm could 'win' parity by naming everything."""
    r = check_parity.grade(
        {"redundant_indexes": ["tenant_id_1", "email_1",
                               "tenant_id_1_status_1", "customer_id_1", "_id_"],
         "reason": "prefix duplicate"}, expected)
    assert r["parity"] is False and len(r["false_positives"]) >= 3


def test_parity_requires_a_stated_mechanism(expected):
    """Right names with no reasoning is a lucky guess, not a diagnosis."""
    r = check_parity.grade(
        {"redundant_indexes": ["tenant_id_1", "email_1"],
         "reason": "these should be dropped"}, expected)
    assert r["parity"] is False and r["unjustified"]


def test_parity_tolerates_formatting_differences(expected):
    """Failing over `accounts.tenant_id_1` would grade prose, not correctness."""
    r = check_parity.grade(
        {"redundant_indexes": ["accounts.tenant_id_1", "  EMAIL_1 "],
         "reason": "prefix of the compound index; duplicate key"}, expected)
    assert r["parity"] is True, r


# ---------------------------------------------------------------------------
# cost aggregation
# ---------------------------------------------------------------------------
def _summarizer():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_sum", BENCH / "summarize.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cost_excludes_runs_that_failed_parity():
    """THE headline rule.

    A route that is cheaper because it answered wrong has saved nothing.
    Averaging its tokens in would manufacture a saving out of a failure — and
    the failing run is typically the cheapest, so the bias is large.
    """
    m = _summarizer()
    runs = [
        {"arm": "route-script", "parity": True,  "tokens_available": 1,
         "tokens_fresh_input": 10000, "ai_credits": 10.0},
        {"arm": "route-script", "parity": False, "tokens_available": 1,
         "tokens_fresh_input": 100,   "ai_credits": 0.1},   # wrong AND cheapest
        {"arm": "route-text",   "parity": True,  "tokens_available": 1,
         "tokens_fresh_input": 50000, "ai_credits": 50.0},
    ]
    s = m.summarise(runs)
    assert s["route-script"]["cost"]["tokens_fresh_input"] == 10000, (
        "the parity-failing run was averaged into the cost, inventing a saving"
    )
    assert s["route-script"]["parity_rate"] == pytest.approx(0.5)


def test_missing_token_data_is_excluded_not_zeroed():
    m = _summarizer()
    runs = [
        {"arm": "route-text", "parity": True, "tokens_available": 1,
         "tokens_fresh_input": 40000},
        {"arm": "route-text", "parity": True, "tokens_available": 0},
    ]
    s = m.summarise(runs)
    assert s["route-text"]["cost"]["tokens_fresh_input"] == 40000
    assert s["route-text"]["missing_token_data"] == 1


def test_report_warns_when_the_cheaper_route_is_less_correct():
    """If the script route wins on tokens but loses on correctness, the saving
    must be flagged as suspect rather than published as a win."""
    m = _summarizer()
    runs = [
        {"arm": "route-text", "parity": True, "tokens_available": 1,
         "tokens_fresh_input": 50000, "ai_credits": 50.0},
        {"arm": "route-script", "parity": True, "tokens_available": 1,
         "tokens_fresh_input": 9000, "ai_credits": 9.0},
        {"arm": "route-script", "parity": False, "tokens_available": 1,
         "tokens_fresh_input": 500, "ai_credits": 0.5},
    ]
    out = m.render(m.summarise(runs), runs)
    assert "suspect" in out.lower()

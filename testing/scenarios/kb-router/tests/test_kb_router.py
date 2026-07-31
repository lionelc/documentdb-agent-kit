"""Contract tests for the knowledge-base router (kb_route.py + kb-route.sh).

Container-independent: the router is a pure text layer, so these tests import the
routing engine directly and also exercise the shell wrapper via subprocess. No
seeded database is used.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import kit

KB_DIR = kit.REPO_DIR / "knowledge-base"
KB_JSON = KB_DIR / "kb.json"
KB_SH = KB_DIR / "kb-route.sh"


def _load_engine():
    """Import knowledge-base/kb_route.py as a module (it has no import-time deps)."""
    spec = importlib.util.spec_from_file_location("kb_route", KB_DIR / "kb_route.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def engine():
    return _load_engine()


@pytest.fixture(scope="session")
def kb():
    with open(KB_JSON) as fh:
        return json.load(fh)


def _route(engine, kb, query):
    """Top (score, tool, hits) for a query."""
    return engine.rank_tools(kb, query)[0]


# ── routing correctness (data-driven from expected-findings.yaml) ───────────
def _route_cases():
    import yaml
    spec = yaml.safe_load((Path(__file__).resolve().parents[1] /
                           "expected-findings.yaml").read_text())
    return [(r["query"], r["tool"]) for r in spec["routes"]]


@pytest.mark.kbrouter
@pytest.mark.parametrize("query,expected_tool", _route_cases())
def test_query_routes_to_expected_tool(engine, kb, query, expected_tool):
    score, tool, hits = _route(engine, kb, query)
    assert tool["id"] == expected_tool, (
        f"'{query}' routed to '{tool['id']}' (score {score:.2f}), "
        f"expected '{expected_tool}'"
    )


@pytest.mark.kbrouter
def test_confident_routes_clear_threshold(engine, kb, expected):
    thr = expected["min_confident_score"]
    for query, _ in _route_cases():
        score, tool, _ = _route(engine, kb, query)
        assert score >= thr, (
            f"'{query}' scored {score:.2f} for '{tool['id']}', "
            f"below confident threshold {thr}"
        )


# ── scoring transparency: the multiword-phrase (+3.0) rule ──────────────────
@pytest.mark.kbrouter
def test_multiword_phrase_matches_and_scores(engine, kb, expected):
    case = expected["phrase_case"]
    score, tool, hits = _route(engine, kb, case["query"])
    assert tool["id"] == case["tool"]
    assert case["keyword"] in hits, (
        f"expected multiword keyword '{case['keyword']}' in matched hits {hits}"
    )
    # a single multiword phrase hit alone is worth +3.0
    assert score >= 3.0, f"multiword phrase should score >= 3.0, got {score:.2f}"


@pytest.mark.kbrouter
def test_gibberish_is_not_confident(engine, kb):
    """A query matching nothing must not produce a confident route."""
    score, _, hits = _route(engine, kb, "qwerty zxcvb asdfg")
    assert score <= 0, f"gibberish scored {score:.2f} with hits {hits}"


@pytest.mark.kbrouter
def test_vague_query_declines_rather_than_guesses(engine, kb, expected):
    """A vague query with no tool-specific signal must fall below the confident
    threshold — the router should decline instead of over-confidently guessing."""
    query = expected["unconfident_case"]["query"]
    score, tool, _ = _route(engine, kb, query)
    thr = expected["min_confident_score"]
    assert score < thr, (
        f"vague query '{query}' should be below the confident threshold {thr}, "
        f"but scored {score:.2f} for '{tool['id']}'"
    )


# ── shell wrapper end-to-end (guards the bash -> kb_route.py env-var seam) ───
@pytest.mark.kbrouter
def test_shell_wrapper_emits_valid_json(engine, kb):
    p = subprocess.run(
        ["bash", str(KB_SH), "--json", "--db", "mydb",
         "diagnose TOAST detoast overhead"],
        capture_output=True, text=True, timeout=30,
    )
    assert p.returncode == 0, f"kb-route.sh failed: {p.stderr}"
    data = json.loads(p.stdout)  # raises if the wrapper leaked non-JSON
    assert data["match"]["tool"] == "document-bloat-advisor"
    assert data["confident"] is True
    assert data["match"]["command"].startswith("bash scripts/document-bloat-advisor.sh")

"""Static validation of the MSBench benchmark (Loop C).

WHY THIS EXISTS
---------------
MSBench's feedback loop is slow and expensive: build images, push to an
internal ACR, submit a run, wait. A typo in a registration file or a broken
arm split should not cost a build cycle to discover — and a *silently* broken
arm split would not be discovered at all, it would just produce a wrong
published number.

These tests need no Docker, no MSBench access and no network, so they run on
every PR. They pin the things the live platform validates (and a few it does
not).

The registration schema was read from the live central benchmarks repo, whose
`skillsbench` / `skillsbenchnoskills` pair is the convention this benchmark
follows.
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

import kit

pytestmark = pytest.mark.benchmarkconfig

BENCH = kit.REPO_DIR / "benchmarks" / "documentdb-sdk-skills"
REG = BENCH / "msbench-registration"
TREATMENT = "documentdb-sdk-skills"
CONTROL = "documentdb-sdk-skills-noskills"

# The keys the live platform's registry.json files carry. Cosmos' registration
# has none of this — it predates the requirement — which is exactly why it is
# asserted here.
REQUIRED_REGISTRY_KEYS = {
    "id", "name", "owner", "creator", "contactEmail", "description",
    "source", "format", "category", "license", "languages", "platforms",
}


def _json(path: Path) -> dict:
    assert path.is_file(), f"missing: {path}"
    return json.loads(path.read_text())


def _toml(path: Path) -> dict:
    assert path.is_file(), f"missing: {path}"
    return tomllib.loads(path.read_text())


def _jsonl(path: Path) -> list[dict]:
    assert path.is_file(), f"missing: {path}"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# registration files
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("arm", [TREATMENT, CONTROL])
def test_registry_json_has_the_required_keys(arm):
    reg = _json(REG / arm / "registry.json")
    missing = REQUIRED_REGISTRY_KEYS - set(reg)
    assert not missing, (
        f"{arm}/registry.json is missing {sorted(missing)}. The live platform "
        f"requires these; copying the Cosmos registration (which has no "
        f"registry.json at all) would be rejected."
    )
    assert reg["id"] == arm, f"registry id {reg['id']!r} != folder {arm!r}"
    assert reg["format"] == "Harbor"


@pytest.mark.parametrize("arm", [TREATMENT, CONTROL])
def test_loader_name_matches_the_arm(arm):
    loader = _toml(REG / arm / "benchmark_loaders.toml")
    assert loader["benchmark"]["name"] == arm
    assert loader["benchmark"]["path"] == "dataset.jsonl"


@pytest.mark.parametrize("arm", [TREATMENT, CONTROL])
def test_dataset_rows_are_well_formed(arm):
    rows = _jsonl(REG / arm / "dataset.jsonl")
    assert rows, f"{arm}/dataset.jsonl is empty"
    for row in rows:
        for key in ("benchmark", "instance_id", "image_tag",
                    "problem_statement", "task_style"):
            assert key in row, f"{arm} dataset row missing {key!r}: {row}"
        assert row["benchmark"] == arm
        assert row["image_tag"].startswith(f"{arm}."), (
            f"image_tag {row['image_tag']!r} must be namespaced by the "
            f"benchmark name, or the two arms will collide in the registry."
        )


def test_the_two_arms_grade_the_same_task():
    """The arms must differ ONLY in whether skills are installed.

    If the control ran a different task, the delta between them would measure
    the task difference rather than the kit.
    """
    t = _jsonl(REG / TREATMENT / "dataset.jsonl")
    c = _jsonl(REG / CONTROL / "dataset.jsonl")
    assert [r["instance_id"] for r in t] == [r["instance_id"] for r in c]
    assert [r["problem_statement"] for r in t] == [r["problem_statement"] for r in c]
    assert [r["sdk"] for r in t] == [r["sdk"] for r in c]


def test_control_arm_is_described_as_a_control():
    reg = _json(REG / CONTROL / "registry.json")
    blob = (reg["description"] + " " + reg.get("notes", "")).lower()
    assert "control" in blob and "no " in blob, (
        "The control arm's registry entry must say it is a control with no "
        "skills, or a reader will treat its score as a standalone result."
    )


# ---------------------------------------------------------------------------
# the task
# ---------------------------------------------------------------------------
TASK = BENCH / "tasks" / "orders-api-python"


def test_task_has_the_harbor_layout():
    for rel in ("task.toml", "instruction.md", "environment/Dockerfile",
                "solution/solve.sh", "tests/test.sh", "tests/checks.py"):
        assert (TASK / rel).exists(), f"task is missing {rel}"


def test_instruction_never_hints_at_the_skills():
    """The organic-discovery protocol.

    The task statement may describe REQUIREMENTS (including scale), but must
    not name the solution. Mentioning indexes, ESR or connection pooling would
    hand the agent the very thing the benchmark is measuring, and both arms
    would score the same.
    """
    text = (TASK / "instruction.md").read_text().lower()
    banned = [
        "create_index", "createindex", "compound index", "esr",
        "connection pool", "singleton", "best practice", "skill",
        "schemaversion", "discriminator",
    ]
    found = [b for b in banned if b in text]
    assert not found, (
        f"instruction.md hints at the solution: {found}. The agent must derive "
        f"these from its installed skills, not from the prompt — otherwise the "
        f"control arm scores the same and the benchmark measures nothing."
    )


def test_instruction_states_the_scale_requirement():
    """Requirements are fair game and necessary: without a scale signal, not
    creating an index is a defensible engineering choice rather than a miss."""
    text = (TASK / "instruction.md").read_text().lower()
    assert "million" in text or "scale" in text, (
        "instruction.md gives no scale signal, so grading index usage would be "
        "unfair — on a small collection, no index is the right answer."
    )


def test_task_toml_declares_timeouts():
    task = _toml(TASK / "task.toml")
    assert task["verifier"]["timeout_sec"] > 0
    assert task["agent"]["timeout_sec"] > 0
    assert task["environment"]["build_timeout_sec"] > 0


# ---------------------------------------------------------------------------
# curation config
# ---------------------------------------------------------------------------
def test_no_verification_is_skipped():
    """Under a BINARY reward, a flaky check corrupts the entire signal.

    The platform's own skillsbench config carries several
    `skip = "oracle", reason = "Non-deterministic: ..."` entries. A check that
    cannot be made deterministic must be REMOVED, not skipped — so this must
    stay empty, and changing it should require a deliberate argument.
    """
    cfg = _toml(BENCH / "orders.toml")
    skips = cfg.get("tasks", {}).get("skip-verification", {})
    assert not skips, (
        f"verification skips declared: {skips}. Make the check deterministic "
        f"or delete it; do not skip it under a binary reward."
    )


def test_curation_registries_match_the_platform():
    cfg = _toml(BENCH / "orders.toml")
    assert cfg["docker"]["prod"]["registry"] == "codeexecservice.azurecr.io"
    assert cfg["docker"]["staging"]["registry"] == "msbenchstaging.azurecr.io"
    for profile in ("local", "staging", "prod"):
        assert cfg["docker"][profile]["benchmark"] == TREATMENT


# ---------------------------------------------------------------------------
# verifier wiring
# ---------------------------------------------------------------------------
VERIFIER = BENCH / "shared" / "verifier"


def test_every_check_module_is_graded():
    """A check module that exists but is never passed to pytest silently
    reduces the graded surface, and nothing else would reveal it."""
    runner = (VERIFIER / "runner.sh").read_text()
    modules = sorted(p.name for p in VERIFIER.glob("check_*.py"))
    assert modules, "no check modules found"
    missing = [m for m in modules if m not in runner]
    assert not missing, (
        f"these check modules exist but runner.sh never runs them: {missing}"
    )


def test_runner_writes_a_reward_before_it_can_fail():
    """Harbor reads reward.txt. If an early failure left it absent, the harness
    would have to guess — so it is written as 0 up front."""
    runner = (VERIFIER / "runner.sh").read_text()
    reward_init = runner.index('echo "0" > "$REWARD_FILE"')
    first_fail = runner.index("start-documentdb")
    assert reward_init < first_fail, (
        "runner.sh must default reward.txt to 0 before the first step that can fail"
    )


def test_metric_harvest_cannot_change_the_reward():
    """Cost telemetry is advisory. Losing it must never turn a passing
    submission into a failing one."""
    runner = (VERIFIER / "runner.sh").read_text()
    idx = runner.index("harvest_metrics.py")
    tail = runner[idx:]
    assert "||" in tail and "WARNING" in tail, (
        "the harvest step must tolerate failure (|| warn), not abort the run"
    )
    assert runner.index('echo "1" > "$REWARD_FILE"') < idx, (
        "the reward must be decided before metrics are harvested"
    )


def test_contract_declares_the_engine_expectations():
    """The engine checks are this benchmark's differentiator; a contract that
    omitted them would silently skip them."""
    contract = _json(BENCH / "shared" / "contracts" / "orders.json")
    root = contract["roots"][0]
    assert root["engine"]["forbid_full_scan_for"], "no engine expectations"
    assert root["engine"]["max_scan_amplification"] > 0
    assert root["indexing"]["esr_compound"]["equality"]
    assert root["indexing"]["esr_compound"]["sort"]


def test_runner_fails_loudly_when_the_treatment_arm_has_no_skills():
    ces = (BENCH / "shared" / "ces" / "runner.sh").read_text()
    assert "FATAL" in ces and "exit 1" in ces, (
        "the agent runner must abort when SKILLS_ARM=kit but the skills are "
        "missing; otherwise the treatment arm silently becomes a control arm"
    )


# ---------------------------------------------------------------------------
# interpreter compatibility
# ---------------------------------------------------------------------------
def test_verifier_modules_parse_under_python_310():
    """The task image is Ubuntu 22.04 => CPython 3.10.

    This caught a real bug: an f-string using 3.12-only nested quoting parsed
    fine on the dev machine (3.12) and blew up inside the container with
    `SyntaxError: unterminated string literal`, which only surfaced after a
    full image build and run. Feature-version parsing catches it in CI in
    milliseconds instead.
    """
    import ast

    modules = sorted((VERIFIER).glob("*.py"))
    assert modules, "no verifier modules found"
    failures = []
    for path in modules:
        try:
            ast.parse(path.read_text(), filename=str(path),
                      feature_version=(3, 10))
        except SyntaxError as exc:
            failures.append(f"{path.name}:{exc.lineno}: {exc.msg}")
    assert not failures, (
        "verifier modules are not valid Python 3.10 (the task image's "
        "interpreter):\n  " + "\n  ".join(failures)
    )


def test_reference_app_parses_under_python_310():
    import ast

    app = TASK / "environment" / "reference" / "app.py"
    try:
        ast.parse(app.read_text(), filename=str(app), feature_version=(3, 10))
    except SyntaxError as exc:
        pytest.fail(f"reference app is not valid Python 3.10: "
                    f"line {exc.lineno}: {exc.msg}")


def test_verifier_has_no_catastrophically_backtracking_regexes():
    """Guard against a real bug that cost a full build-and-run cycle to find.

    check_source.py originally detected per-request client construction with a
    regex containing NESTED QUANTIFIERS over lines:

        (?:[^\\n]*\\n(?:[ \\t]+[^\\n]*\\n)*?)*?

    On a 6 KB file it never returned — the verifier hung for minutes and the
    run had to be killed. It is now done with `ast`, which is exact and ~1000x
    faster.

    A quantifier applied to a group that itself contains a quantifier is the
    signature of the problem, so it is banned outright in this directory.
    """
    import re as _re

    # A group ending in a quantifier, immediately followed by another quantifier.
    nested = _re.compile(r"\)[*+]\??[*+]|\*\?\)\*|\)\*\?\)")
    offenders = []
    for path in sorted(VERIFIER.glob("*.py")):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or '"""' in stripped:
                continue
            if nested.search(line):
                offenders.append(f"{path.name}:{lineno}")
    assert not offenders, (
        "possible catastrophic-backtracking regex (a quantified group followed "
        f"by another quantifier) at {offenders}. Use ast for source analysis."
    )


# ---------------------------------------------------------------------------
# credential detection must not fire on correct code
# ---------------------------------------------------------------------------
def _credential_findings(source: str) -> list[str]:
    """Apply check_skills.py's credential patterns to a source string."""
    import re as _re
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_cs", VERIFIER / "check_skills.py")
    mod = importlib.util.module_from_spec(spec)
    # check_skills imports pytest at module scope; the test venv has it.
    spec.loader.exec_module(mod)
    out = []
    for pattern, label in mod._CREDENTIAL_PATTERNS:
        for m in _re.finditer(pattern, source):
            out.append(f"{label}: {m.group(0)[:40]}")
    return out


def test_credential_check_does_not_fire_on_env_driven_uris():
    """A false positive here is worse than no check at all.

    This exact pattern failed the reference implementation: the URI is an
    f-string TEMPLATE reading credentials from the environment — the correct
    thing to do — but the password character class matched the interpolation
    placeholder and flagged it as a hardcoded secret.
    """
    good = '''
from urllib.parse import quote_plus
user = os.environ["DOCUMENTDB_USER"]
password = os.environ["DOCUMENTDB_PASSWORD"]
uri = f"mongodb://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/"
uri2 = "mongodb://%s:%s@%s" % (user, password, host)
pwd = os.getenv("DOCUMENTDB_PASSWORD")
'''
    assert not _credential_findings(good), (
        "the credential check fires on correct, env-driven code: "
        f"{_credential_findings(good)}"
    )


def test_credential_check_still_catches_real_secrets():
    """The other half: a check that never fires is worthless."""
    bad_uri = 'client = MongoClient("mongodb://admin:Sup3rSecret@db:10260/")'
    bad_literal = 'password = "Sup3rSecret"'
    assert _credential_findings(bad_uri), "missed a URI-embedded password"
    assert _credential_findings(bad_literal), "missed a hardcoded password literal"


# ---------------------------------------------------------------------------
# singleton-client detection
# ---------------------------------------------------------------------------
def _client_offenders(tmp_path, source: str) -> list[str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_csrc", VERIFIER / "check_source.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = tmp_path / "app.py"
    f.write_text(source)
    return mod._client_calls_inside_functions([f])


def test_singleton_client_detector_accepts_module_level_client(tmp_path):
    good = '''
from pymongo import MongoClient
client = MongoClient("mongodb://host")
db = client["x"]

@app.get("/orders")
def list_orders():
    return list(db.orders.find({}))
'''
    assert not _client_offenders(tmp_path, good)


def test_singleton_client_detector_catches_client_hidden_in_a_helper(tmp_path):
    """Found by a negative control, not by inspection.

    An earlier version of this check only looked inside route-decorated
    functions. A deliberately naive submission that built a client in a plain
    helper called by every route PASSED, even though it creates a new
    connection pool per request — the exact anti-pattern the check exists for.
    """
    sneaky = '''
from pymongo import MongoClient

def coll():
    c = MongoClient("mongodb://host")
    return c["db"]["orders"]

@app.get("/orders")
def list_orders():
    return list(coll().find({}))
'''
    offenders = _client_offenders(tmp_path, sneaky)
    assert offenders, (
        "a MongoClient built inside a helper called per request was not "
        "detected; the check would pass a submission that creates a new "
        "connection pool on every call"
    )


def test_singleton_client_detector_allows_a_memoised_factory(tmp_path):
    """A cached factory really is a singleton, and rejecting it would punish a
    legitimate pattern."""
    cached = '''
from functools import lru_cache
from pymongo import MongoClient

@lru_cache(maxsize=1)
def get_client():
    return MongoClient("mongodb://host")
'''
    assert not _client_offenders(tmp_path, cached)


# ---------------------------------------------------------------------------
# reproducibility of the published numbers
# ---------------------------------------------------------------------------
def test_control_submissions_are_committed():
    """The report cites the naive control's score as evidence.

    That fixture originally lived only in /tmp, which made the headline
    discrimination result impossible for anyone else to reproduce. Evidence
    that cannot be re-run is an assertion, not a measurement.
    """
    naive = BENCH / "controls" / "naive-python"
    for rel in ("app.py", "build.sh", "run.sh", "requirements.txt"):
        assert (naive / rel).is_file(), f"naive control is missing {rel}"


def test_naive_control_is_functional_but_not_best_practice():
    """The fixture only proves anything if it is genuinely a WORKING app that
    merely ignores best practice. If someone 'fixes' it, it stops testing the
    thing it exists to test."""
    src = (BENCH / "controls" / "naive-python" / "app.py").read_text()
    # functional: implements the full contract
    for endpoint in ("/health", "/orders"):
        assert endpoint in src, f"naive control no longer serves {endpoint}"
    assert "insert_one" in src and "find_one" in src, (
        "naive control must really persist to DocumentDB, or it stops being a "
        "test of best practice and becomes a test of basic competence"
    )
    # but deliberately wrong in the ways the kit teaches
    assert "create_index" not in src, (
        "naive control now creates an index; it no longer demonstrates the gap"
    )
    assert "schemaVersion" not in src, "naive control now sets schemaVersion"


def test_verify_controls_script_checks_both_directions():
    """A grader that cannot fail is worthless; one that cannot pass is broken.
    The reproduction script must assert both, plus the case in between."""
    script = (BENCH / "verify-controls.sh").read_text()
    for name, expected in (("oracle", "1"), ("empty", "0"), ("naive", "0")):
        assert f"run_control {name} {expected}" in script, (
            f"verify-controls.sh does not assert {name} -> reward {expected}"
        )
    assert "exit 1" in script, "the script must fail the build when a control deviates"

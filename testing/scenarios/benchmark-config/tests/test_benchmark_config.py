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

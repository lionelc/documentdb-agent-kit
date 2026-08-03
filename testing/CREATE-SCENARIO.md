# Recipe: Create a New Scenario

A scenario proves that one agent-kit diagnostic script reliably detects a class
of known problems (and does not raise false positives). Follow these steps.

## 1. Copy the template

```bash
cp -r scenarios/_scenario-template scenarios/<my-scenario>
```

## 2. Write `fixture.js` — plant known issues deterministically

The fixture is a mongosh script run against a fresh scenario database. Rules:

- **Deterministic**: no randomness in the *structure* of what you plant. The
  same fixture must yield the same findings every run.
- **Self-contained**: drop and recreate every collection it touches.
- **Plant a clear answer key**: each issue you create must map to an expected
  finding. Add a comment naming the rule/category each line triggers.
- If your script differentiates *used* vs *unused* (like the redundancy finder),
  generate query traffic on the indexes/paths that should look healthy.

End with a `FIXTURE_READY <name>` print and a short summary.

## 3. Encode the answer key in `expected-findings.yaml`

Keep it declarative. Prefer **minimum counts** and **membership** assertions over
brittle exact-output matching, so the contract survives small fixture tweaks but
still fails if a whole category is missed. Use `rule_any: [...]` when a label may
vary by threshold (e.g. `UNUSED_VERIFIED` vs `WRITE_TAX`).

## 4. Wire the fixture in `conftest.py`

```python
from pathlib import Path
from conftest_base import make_seeded_db_fixture

seeded_db = make_seeded_db_fixture("test_<unique_db>", Path(__file__).resolve().parent)
```

Use a unique database name per scenario so scenarios don't collide.

## 5. Write `tests/test_*.py`

Use the shared helpers:

```python
import kit

def test_something(seeded_db, expected):
    res = kit.run_script("<script>.sh", "--db", seeded_db, "--json", want_json=True)
    assert res.ok
    ...assert findings match `expected`...
```

- For scripts with `--json` (e.g. `index-redundancy-finder.sh`): parse
  `res.json` and assert on structured findings.
- For text-only scripts (e.g. `data-integrity-check.sh`, `perf-advisor.sh`):
  match stable markers and the `Total ...: N` / `COLLSCAN total: N` counters.

## 6. Calibrate against real output

Run the script once against your seeded fixture and read the *actual* output —
then write the contract to match the script's real, deterministic behavior.
Do **not** hand-wave the expected values; the answer key is the recorded truth.

```bash
cd testing && ../testing-venv/bin/python -m pytest scenarios/<my-scenario> -v
```

## 7. Add a `SCENARIO.md`

Document what is planted and what must be detected, mirroring the existing
scenarios. Mark it as fixed ("do not edit to make a failing test pass").

## Golden rule

> If a test goes red, decide whether it's a **bug** (fix the script) or an
> **intended** behavior change (deliberately update `expected-findings.yaml`).
> Never edit the answer key just to silence a failure.

# Committed results

Benchmark results are **checked in**, so a number quoted in a deck can be traced
to the run that produced it, by someone who was not there.

Raw run output is not. `msbench-cli` emits large per-instance dumps, trajectories
and logs; those stay out of git (see [`.gitignore`](../.gitignore)). What lands
here is the **curated artifact**: a `.json` for tooling and a `.md` for humans,
each carrying enough provenance to re-run it.

## Naming

```
<date>-<what>[-<arm>].{json,md}

2026-08-17-controls-validation.json      grader validation (no arms — not an A/B)
2026-11-04-effectiveness-treatment.json  the skills arm
2026-11-04-effectiveness-control.json    the no-skills arm
2026-11-04-effectiveness.md              the generated comparison
```

## Two rules, both enforced by tests

### 1. Arms come in pairs

An effectiveness result **may not be committed for one arm alone**. A treatment
score with no control is not a result: 80% resolved could mean an excellent kit
or an easy task, and nothing in the number tells you which.

`testing/scenarios/benchmark-config/` fails if a `*-treatment.json` has no
matching `*-control.json`.

> This is the one place the DocumentDB kit deliberately diverges from
> `cosmosdb-agent-kit`, whose committed batch results are all `*-skills.*` with
> no control counterpart — so a reader cannot compute a delta from what is in
> that repo.

### 2. Provenance is mandatory

Every committed result carries a `provenance` block:

| Field | Why |
|---|---|
| `run_id` | the MSBench run, so the raw output can be retrieved |
| `date` | when it ran |
| `benchmark` | which arm produced it |
| `image_tag` | the exact task image — the task can change |
| `dataset_version` | the dataset row set |
| `kit_commit` | the skills the agent had; results are meaningless without it |
| `model` | cross-model comparison is only valid like-for-like |
| `pass_at_k` | attempts per instance |

A result missing any of these cannot be interpreted a year later, so the test
rejects it.

## Generating

```bash
# effectiveness (needs both arms — see docs/REPORT.md §4 stage 5)
msbench-cli report --run_id <treatment> --output results/2026-11-04-effectiveness-treatment.json
msbench-cli report --run_id <control>   --output results/2026-11-04-effectiveness-control.json

python3 report.py \
  --treatment results/2026-11-04-effectiveness-treatment.json \
  --control   results/2026-11-04-effectiveness-control.json \
  --out       results/2026-11-04-effectiveness.md
```

```bash
# grader validation (Docker only, no internal access)
bash verify-controls.sh
```

## What is here now

| File | What |
|---|---|
| [`2026-08-17-controls-validation.json`](2026-08-17-controls-validation.json) | grader validation — oracle / empty / naive |
| [`2026-08-17-controls-validation.md`](2026-08-17-controls-validation.md) | the same, readable |

**No effectiveness results yet** — no MSBench run has been executed. See
[`../docs/REPORT.md`](../docs/REPORT.md).

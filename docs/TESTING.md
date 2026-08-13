# Testing the agent kit

The kit is tested in **two loops with opposite success criteria**. Conflating
them is the main design mistake to avoid.

| | **Loop A — deterministic** | **Loop B — non-deterministic** |
|---|---|---|
| Subject | `scripts/*.sh`, `knowledge-base/kb-route.sh` | the text skills (`skills/**`) driving an agent |
| Question | "Is the answer **stable and repeatable**?" | "Is the output **good**, and what did it **cost**?" |
| Success | identical canonicalised `--json` across N runs | beats its own control arm, at N≈5 |
| Runtime | ~2 min, **free** | minutes to hours, **costs AI credits** |
| Home | [`testing/`](../testing/) | [`evals/`](../evals/) |
| CI | every PR | dispatch / monthly only |

A diagnostic script is a **tool**: the same database must give the same answer
every time. An agent is not: it must be measured as a distribution against a
control. Applying either standard to the other produces nonsense.

---

## Prerequisites

Loop A's `static` scenarios need **nothing at all**. Everything else needs a
running container.

```bash
# 1. Start DocumentDB Local
docker run -d --name documentdb-local \
  -p 10260:10260 -p 9712:9712 \
  -e USERNAME=docdbadmin -e PASSWORD='<choose-a-password>' \
  ghcr.io/microsoft/documentdb/documentdb-local:latest

# 2. Install mongosh INTO the container — the image does not ship it
MV=2.3.8
curl -sSL "https://downloads.mongodb.com/compass/mongosh-${MV}-linux-x64.tgz" -o /tmp/mongosh.tgz
tar xzf /tmp/mongosh.tgz -C /tmp
docker cp "/tmp/mongosh-${MV}-linux-x64/bin/mongosh" documentdb-local:/usr/local/bin/mongosh
docker cp "/tmp/mongosh-${MV}-linux-x64/bin/mongosh_crypt_v1.so" documentdb-local:/usr/local/lib/
docker exec documentdb-local mongosh --version

# 3. Export the password the container was created with
export DB_PASSWORD='<that-password>'
```

> **Step 2 is not optional.** The `documentdb-local` image ships `psql` but **no
> `mongosh`**, and every diagnostic script talks to the database through
> `docker exec <container> mongosh`. Skipping it makes every scenario fail with
> `executable file not found`, which looks like a broken test rather than a
> missing dependency.

Forgot the password?

```bash
docker inspect documentdb-local \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep PASSWORD
```

> **A wrong password reports as `MongoServerError: Invalid key`** — an *auth*
> failure, not a malformed document. The suite now detects this up front and
> aborts once with an actionable message instead of producing ~30 cryptic
> failures.

---

## Loop A — deterministic tests

```bash
bash testing/run.sh                       # everything (~2 min) -> 86 passed
```

`run.sh` creates `testing-venv/` on first use and passes extra arguments
straight through to pytest.

### No container, no credentials, no network

These run in well under a second and are the first CI job:

```bash
cd testing && pytest scenarios/token-accounting scenarios/evals-config
```

They override the container fixture with a no-op. Use them for a fast check that
the cost metrics and the Loop B configs are still sane.

### Individual scenarios

```bash
bash testing/run.sh scenarios/determinism           # scripts are reproducible
bash testing/run.sh scenarios/remediation-effect    # the advice actually works
bash testing/run.sh scenarios/kb-router             # routing contract
bash testing/run.sh -m determinism                  # by marker
bash testing/run.sh -k redundancy -v                # by name
```

Markers: `determinism`, `remediation`, `tokens`, `evalsconfig`, `kbrouter`,
`redundancy`, `integrity`, `perf`, `healthy_indexes`, `jsoncontract`.

### What the two headline scenarios prove

**`scenarios/determinism`** runs every script 3× against one untouched database
and asserts the canonicalised `--json` is identical. It found and drove the fix
of **four real nondeterminism bugs** — two `$sample` calls, a latency threshold
that decided list *membership*, and an `explain()` probe built from an arbitrary
`findOne()`. See [its SCENARIO.md](../testing/scenarios/determinism/SCENARIO.md).

**`scenarios/remediation-effect`** is the strongest grading rung available:
rather than asking a model whether the advice is good, it **applies** the advice
and measures the database.

```
tool detects the defect -> fix DERIVED FROM THE TOOL'S OUTPUT -> plan improves
  -> results unchanged -> no new redundancy -> the tool agrees it is fixed
```

The metric is **scan amplification** (`totalDocsExamined / nReturned`): 2000× →
1×. Raw "documents examined" is the wrong metric on this engine — see
[its SCENARIO.md](../testing/scenarios/remediation-effect/SCENARIO.md).

### Reproducing a determinism check by hand

```bash
for i in 1 2 3; do
  bash scripts/data-integrity-check.sh --db test_determinism --json > /tmp/r$i.json
done
diff /tmp/r1.json /tmp/r2.json && diff /tmp/r2.json /tmp/r3.json && echo IDENTICAL
```

Only `--json` is expected to be stable. The human report embeds a wall-clock
banner and measured latencies by design.

---

## Loop B — cross-model skill evals

Runs on [Vally](https://microsoft.github.io/vally/). **Everything below the
`lint`/`plan` line costs AI credits.**

```bash
cd evals && npm ci
```

### Free — always do these first

```bash
npm run lint              # validate the eval spec
npm run experiment:plan   # resolve the 3x2 matrix, print the plan, spend nothing
npm run eval:mock         # execute against the mock executor
```

> ⚠️ **The mock executor invokes no skills** (`Skills used 0`). Positive-trigger
> stimuli therefore always fail and anti-trigger stimuli pass **vacuously**. The
> mock validates plumbing, not behaviour — never quote a mock result.

### Paid — real models

Requires `COPILOT_SDK_AUTH_TOKEN`.

```bash
# One cell, to sanity-check cost before committing to the matrix
npx vally experiment run documentdb-skills.experiment.yaml \
  --variant 'model=claude-opus-5,skills=kit'

# The full matrix: 3 models x {kit, control} x 5 runs
npm run experiment
```

The matrix is **3 models × 2 arms × 5 runs = 30 trials per stimulus**. Start
with one cell.

### Two rules for reading Loop B results

1. **Only deltas are publishable.** An absolute pass-rate is uninterpretable —
   "90% passed" means nothing without knowing what a bare agent scores on the
   same stimuli. Every model runs with the kit and with nothing.
2. **The agent is never told to use the skills.** They are made discoverable as
   a user would have them installed, and no prompt mentions them. This measures
   the kit's *organic* effect, not a hinted best case.

### Cost accounting

```bash
python3 evals/harness/token_usage.py sessions --limit 10

python3 evals/harness/token_usage.py report --session <id> \
  --task orders-api --model claude-opus-5 --arm skills --run 1 \
  --outcome-passed 40 --outcome-total 40 --out results/opus-skills-1.json

python3 evals/harness/token_usage.py compare results/*.json
```

```
| Model | Arm | N | Pass rate | Credits (mean±sd) | Turns | Fresh input tok | Cache share | Credits/pass |
|---|---|---|---|---|---|---|---|---|
| claude-opus-5 | control | 3 | 67% | 812.4±31.2 | 9.0±1.0 | 402,118 | 95% | 1218.6 |
| claude-opus-5 | skills  | 3 | 100% | 941.7±18.5 | 6.3±0.6 | 486,930 | 95% | 941.7 |
```

Three things this table is built to stop you getting wrong:

- **Never quote raw input tokens as the cost of a skill.** `cache_read_tokens`
  is a *subset* of `input_tokens`, and ~95% of input is cache reads, so the
  skill payload is amortised. `Fresh input tok` is the honestly-billed number.
- **A failed run reports no cost-to-green**, otherwise giving up early would
  look like efficiency. `Credits/pass` divides by *passes*, not runs — failed
  attempts are part of the price.
- **Cells with n < 3 are flagged ⚠️.** A mean over one non-deterministic agent
  run is an anecdote.

---

## The grading ladder

Pick the **strongest** criterion the scenario allows. An LLM judge is the last
resort, not the default.

| Rung | Criterion | Used by |
|---|---|---|
| 1 | Determinism (identical output) | `scenarios/determinism` |
| 2 | **Before/after measured delta** | `scenarios/remediation-effect` |
| 3 | Structural assertion | `scenarios/*-contract`, `evals-config` |
| 4 | Semantic equivalence | query-generation scenarios |
| 5 | Behavioural (does it run and do the right thing?) | future app-level evals |
| 6 | Contract conformance | `scenarios/json-contract` |
| 7 | LLM-as-a-judge | only irreducibly subjective items |

Improvement metrics are gameable, so they are **paired with regression guards** —
`remediation-effect` runs `index-redundancy-finder.sh` to make sure "just index
everything" fails, and asserts the result set is unchanged.

---

## CI

| Workflow | Trigger | Cost |
|---|---|---|
| [`loop-a-tests.yml`](../.github/workflows/loop-a-tests.yml) | push, PR, dispatch | free |
| [`loop-b-evals.yml`](../.github/workflows/loop-b-evals.yml) | dispatch, monthly | credits |

Loop B's `validate` job (static guards + `vally lint` + matrix resolve) always
runs and is free, so a broken skill path is caught **before** any credits are
spent. That matters: `vally --dry-run` validates matrix structure but **not**
skill paths, and a treatment arm whose skills fail to load is silently just a
second control arm.

Use the `dry_run` input to validate the matrix from CI for free.

---

## Adding a scenario

See [`testing/CREATE-SCENARIO.md`](../testing/CREATE-SCENARIO.md) and the
template at `testing/scenarios/_scenario-template/`.

Two rules learned the hard way:

- **Seed deterministically.** No `Math.random()` in a fixture — use a seeded
  LCG. A test that cannot be reproduced cannot be debugged.
- **Prove the test can fail.** Inject a mutation and confirm it is caught. Every
  scenario here documents the mutations it was verified against; a green suite
  that cannot fail proves nothing.

# MSBench effectiveness report

**Status as of 2026-08-13 (`5659218`): NO MSBENCH RUN HAS BEEN EXECUTED.**

There is therefore **no effectiveness data yet** — no skills-on vs skills-off
comparison, and no agent token usage. This document records what *has* been
measured, states plainly what has not, and shows how to produce the real report
once a run exists.

> Any number in a GTM deck must come from the generated report described in
> [§4](#4-how-to-produce-the-real-report), not from this page.

---

## 0. What "treatment" and "control" mean here

Borrowed from experimental design: you change **one** thing and hold everything
else fixed, so any difference in the result is attributable to that one thing.

**The treatment is: the DocumentDB agent kit's skills are installed and
discoverable.** That is the entire intervention.

| | Control arm | Treatment arm |
|---|---|---|
| Benchmark | `documentdb-sdk-skills-noskills` | `documentdb-sdk-skills` |
| `~/.copilot/skills/` | **empty** | **17 SKILL.md files** copied in |
| Task, prompt, API contract | identical | identical |
| Model, agent, container, verifier | identical | identical |
| Is the agent told to use the skills? | n/a | **no — never mentioned** |

Implemented in [`shared/ces/runner.sh`](../shared/ces/runner.sh): `SKILLS_ARM=kit`
copies the skills into the agent's personal skills directory; `SKILLS_ARM=control`
installs nothing and deletes the directory defensively, so a stale image layer
cannot leak skills into the control.

### What that means for the TOKEN comparison specifically

The token delta answers: **what does having the kit installed cost?**

- **Control:** there are no skill files, so there is nothing for the agent to
  discover or read. Its input tokens are the task and its own work.
- **Treatment:** the skills are on disk. When the agent judges one relevant it
  *reads* the `SKILL.md`, and those bytes become input tokens.

So `tokens_fresh_input(treatment) − tokens_fresh_input(control)` is, quite
literally, the price of the kit being available and used.

Two things stop that number from being read naively:

1. **Skills are cached.** A payload is sent once and then served from cache
   (~92% of input was cache reads in practice), so raw `tokens_input` badly
   overstates the marginal cost. The report leads with *fresh* (uncached) input.
2. **More tokens per attempt is not the same as more expensive.** "Skills add
   context, therefore skills cost more" is trivially true and uninteresting. The
   question is whether that extra context buys **fewer attempts and more
   successes** — which is why the headline cost figure is *credits per passing
   result*, not credits per run.

The hypothesis being tested is: treatment spends **more per attempt**, needs
**fewer turns**, passes **more often**, and therefore costs **less per success**.
If the run shows otherwise, that is a finding we need, not a result to bury.

### Why not just run it once and look at the number?

Because an absolute score is uninterpretable. If the treatment arm resolves 80%
of attempts, that could mean the kit is excellent — or that the task is easy
enough for any competent agent. Only the control tells you which.
[`report.py`](../report.py) refuses to produce a report from a single arm for
this reason.

---

## 1. What has been measured

The benchmark's **grader** has been validated end-to-end on a local build. This
proves the instrument works. It says nothing about whether the kit helps — no
agent has attempted the task.

| Submission | Reward | Checks |
|---|---|---|
| Oracle (reference implementation) | **1** | 31 / 31 |
| Empty `/app` | **0** | fails at deliverables |
| **Working-but-naive app** | **0** | 20 / 30 — 10 failed |

*(The naive run grades 30 rather than 31 because the ESR ordering check is
skipped when no compound index exists at all — a skipped check is not counted as
a pass or a failure.)*

### Why the naive control is the meaningful one

An empty `/app` failing only proves the harness notices missing files. The naive
app is **fully functional**: correct HTTP behaviour, correct persistence,
duplicate rejection, right result sets. It passes every API and behavioural
check and still scores 0, failing exactly the best-practice checks:

Measured per-category result for that submission:

| Check category | Naive | Oracle | What it covers |
|---|---|---|---|
| `api` | **6/6** | 6/6 | endpoints, status codes, payloads |
| `behavior` | **6/6** | 6/6 | real persistence, round-trip, no duplicates |
| `documentdb` | **0/5** | 6/6 | discriminator, schemaVersion, timestamp, indexing |
| `engine` | **2/4** | 4/4 | query plan, scan amplification |
| `source` | **1/4** | 4/4 | singleton client, pool/timeouts, TLS |
| `skills` | **4/4** | 4/4 | no hardcoded creds, env-driven config |

That is the discrimination the benchmark exists to provide: **basic competence
is perfect (12/12) while best practices collapse (3/13)**. It separates the two
cleanly, which is exactly what a skills benchmark must do.

This is also a useful prior for what the **control arm** may look like. It is a
prior, not a prediction — a real agent is not this app, and may do better or
worse.

### Cost pipeline — proven, but with no agent data

Token harvesting was verified inside the task container by mounting a real
Copilot CLI session store. `custom_metrics.json` was written with
`tokens_available: 1` and populated fields:

```json
{
  "tokens_fresh_input": 148301071,
  "tokens_cache_read":  1618077206,
  "cache_read_share_pct": 91.6,
  "ai_credits": 194081.25,
  "credits_to_green": 194081.25,
  "checks_engine_passed": 4,  "checks_engine_total": 4,
  "reward": 1, "tokens_available": 1
}
```

⚠️ **Those numbers are a plumbing demonstration, not a result.** They are the
usage of an interactive development session that was mounted in to exercise the
code path. The oracle is a `cp` of a reference implementation, not an agent, so
it consumes no tokens of its own. Real figures require an agent run.

One number *is* generalisable and worth carrying into the analysis:
**91.6% of input tokens were cache reads.** Skill payloads are sent once and
then served from cache, which is why the report leads with fresh (uncached)
input rather than raw `tokens_input`.

---

## 2. What has NOT been measured

| Question | Status |
|---|---|
| Does the kit raise the pass rate? | ⬜ **unknown** — no agent run |
| What does a task cost with vs without the kit? | ⬜ **unknown** |
| Which check categories does the kit move? | ⬜ **unknown** |
| `pass@k` reliability across attempts | ⬜ **unknown** |
| Does it hold across models? | ⬜ out of scope here (that is Loop B) |

Blocking work, in order:

1. Push both task images to the internal ACR (`harbor-format-curation`).
2. PR `msbench-registration/` into the central repo under
   `benchmarks/skillsbench/`.
3. Run **both** arms with `--pass_at_k 5`.

---

## 3. The report this will produce

Generated by [`report.py`](../report.py). Shape shown here with **illustrative
placeholder values** so reviewers can agree the format before the run:

```
| | Control | Treatment | Delta |
|---|---|---|---|
| Instances       |   5 |   5 |     |
| Resolved        |   1 |   4 |  +3 |
| **Pass rate**   | 20% | 80% | +60% |

| Metric             | Control | Treatment | Delta    |
|--------------------|---------|-----------|----------|
| Fresh input tokens | 403,718 | 488,730   | +85,012  |
| AI credits         |  832.40 |   965.70  |  +133.3  |
| Turns              |     9.8 |      6.6  |    -3.2  |

| Derived                         | Control  | Treatment |
| **Credits per passing result**  | 4,162.00 |  1,207.12 |

| Check category | Control | Treatment | Delta |
| `api`          |    100% |      100% |   +0% |
| `behavior`     |    100% |      100% |   +0% |
| `documentdb`   |     33% |       83% |  +50% |
| `engine`       |     20% |       80% |  +60% |
| `source`       |     60% |       90% |  +30% |
```

**These are placeholders, not findings.** They illustrate the hypothesis the
run will test: the kit costs *more per attempt* but needs *fewer attempts*, so
cost per passing result falls, and the movement concentrates in the
`documentdb` / `engine` / `source` categories while `api` / `behavior` stay flat
in both arms.

If the real run contradicts that — for instance if `api`/`behavior` also move,
suggesting the control arm is simply worse at the basic task — the benchmark
design needs revisiting, not the write-up.

---

## 4. How to produce the real report

```bash
export PATH="$HOME/pgmongo/msbench-tools/venv/bin:$PATH"
az login

# 1. Run BOTH arms. A one-armed number is not publishable.
msbench-cli run --benchmark documentdb-sdk-skills \
  --dataset benchmarks/documentdb-sdk-skills/msbench-registration/documentdb-sdk-skills/dataset.jsonl \
  --pass_at_k 5 --runner benchmarks/documentdb-sdk-skills/shared/ces/runner.sh

msbench-cli run --benchmark documentdb-sdk-skills-noskills \
  --dataset benchmarks/documentdb-sdk-skills/msbench-registration/documentdb-sdk-skills-noskills/dataset.jsonl \
  --pass_at_k 5 --runner benchmarks/documentdb-sdk-skills/shared/ces/runner.sh

# 2. Export per-instance data (this is what carries the token metrics)
msbench-cli report --run_id <treatment-run-id> --output treatment.json
msbench-cli report --run_id <control-run-id>   --output control.json

# 3. Generate the report
python3 benchmarks/documentdb-sdk-skills/report.py \
  --treatment treatment.json --control control.json \
  --out benchmarks/documentdb-sdk-skills/docs/REPORT.md
```

`report.py --json` emits the same summary as machine-readable JSON.

---

## 5. Reading the numbers honestly

Four traps, each guarded by a test in
`testing/scenarios/benchmark-metrics/`:

**Never quote `tokens_input` as the cost of the kit.** `cache_read_tokens` is a
*subset* of it, and ~92% of input is cache reads. Use `tokens_fresh_input`.

**A pass rate without a control arm means nothing.** `report.py` refuses to run
on one arm for this reason. 80% could be an excellent kit or an easy task.

**Cost per *passing result*, not per run.** Failed attempts are part of the
price of a success, so credits are divided by passes. A treatment arm that costs
more per attempt but passes far more often is cheaper where it counts.

**`tokens_available: 0` means "not measured", never "free".** Instances missing
token data are excluded from cost means and reported separately, so a
harvesting failure cannot quietly drag an average down.

Also: agent runs are non-deterministic. `report.py` flags any arm with fewer
than 3 instances as indicative rather than measured, and `--pass_at_k 5` exists
so a single lucky or unlucky attempt does not become the headline.

---

## 6. Where each number comes from in the code

| Number | Written by | Read by |
|---|---|---|
| `reward` (0/1) | `shared/verifier/runner.sh` → `/logs/verifier/reward.txt` | MSBench (Harbor contract) |
| per-check results | `pytest --ctrf` → `/logs/verifier/ctrf.json` | `harvest_metrics.py` |
| `checks_<category>_*` | `harvest_metrics.py: read_ctrf()` | `report.py` |
| token counts, `ai_credits` | `harvest_metrics.py: read_usage()`, from the Copilot CLI session store | `report.py` |
| `custom_metrics.json` | `harvest_metrics.py: main()` → `$OUTPUT_DIR` | `msbench-cli report` |
| `resolved`, `pass_at_k_status` | MSBench | `report.py: summarise()` |
| the tables above | `report.py: render()` | you |

Inspect any layer directly:

```bash
# the metric artifact, from a local run
docker run --rm -v "$PWD/tests:/tests:ro" -v "$PWD/solution:/solution:ro" \
  documentdb-orders-api-python:latest \
  bash -c '/solution/solve.sh >/dev/null && /tests/test.sh >/dev/null 2>&1; \
           cat /output/custom_metrics.json'

# the same code, against your own Copilot session store
python3 benchmarks/documentdb-sdk-skills/shared/verifier/harvest_metrics.py \
  --store ~/.copilot/session-store.db --output-dir /tmp/out && cat /tmp/out/custom_metrics.json

# the Loop B equivalent (same cost definitions, pinned equal by test)
python3 evals/harness/token_usage.py sessions --limit 10

# the guards on all of the above
cd testing && pytest scenarios/benchmark-metrics scenarios/benchmark-config
```

The two cost implementations (`harvest_metrics.py` for Loop C,
`evals/harness/token_usage.py` for Loop B) cannot share an import — the
harvester must run inside a minimal task container — so
`test_harvester_agrees_with_the_loop_b_cost_module` pins them to identical
output instead. If they ever diverge, that test fails rather than the two
publishing different costs for the same run.

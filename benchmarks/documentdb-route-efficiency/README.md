# Route efficiency: text skills vs diagnostic scripts

Replaces [`token-tests/`](../../token-tests/) with a **measured** comparison.

## What changed, and why the numbers may move

`token-tests/` never calls a model. It counts bytes with `wc -c` and converts
with `tokens ≈ bytes/4`. Its headline — *52–97% saving, median 77%* — is a
**payload-size estimate**, not consumption.

Three things that proxy cannot see, each capable of moving the result in a
different direction:

| Missing from the proxy | Likely direction |
|---|---|
| **Caching.** A `SKILL.md` is sent once then served from cache (~91% of real input is cache reads), so its marginal cost is far below `bytes/4`. | **shrinks** the text arm's cost → *less* saving than claimed |
| **Turns.** The text arm must run its own queries and interpret raw output, probably over several turns, each re-sending context. | **grows** the text arm's cost → *more* saving than claimed |
| **Output + reasoning tokens.** Absent entirely from the proxy. | unknown |

So this benchmark may well contradict the published figure. That is the point of
measuring.

---

## The two arms

The intervention is **which route the kit exposes**, and nothing else.

| | Control — `route-text` | Treatment — `route-script` |
|---|---|---|
| `~/.copilot/skills/` | the kit's **text skills** | *(empty)* |
| `scripts/`, `knowledge-base/` | **absent** | **present** |
| How it answers | reads a `SKILL.md`, runs its own `mongosh` / `psql`, interprets raw output | routes with `kb-route.sh`, runs one read-only script, reads the compact verdict |
| Database | identical fixture | identical fixture |
| Question asked | identical | identical |

Both arms are told the same thing and neither is told which route it has. The
arm is expressed purely by what exists on disk — `shared/arms/install-arm.sh`.

### Why not "agent chooses"?

A third design — install both and see which it picks — measures something
different and more realistic, but it cannot answer *this* question: it would
confound "how expensive is each route" with "how good is the agent at choosing".
Worth doing later as a separate task; it is not this one.

---

## Preventing leakage

Leakage would flatter whichever arm runs second, so every shared surface is
reset. This is the part most easily got wrong.

| Leak | Why it matters here | Control |
|---|---|---|
| **Conversation history** | a second run could answer from the first run's reasoning | one fresh agent session per run; no multi-turn reuse across runs |
| **Prompt cache** | a warm cache makes the same payload cost far less | arm order is **randomised per iteration**, so warmth cannot systematically favour one arm |
| **Database state** | `$indexStats` / `idx_scan` counters accumulate; `index-redundancy-finder`'s *unused* findings depend on them, and the old `token-tests` README documents exactly this volatility (52% → 93% depending on warmth) | **a fresh database per run**, uniquely named, seeded from the same deterministic fixture |
| **Planner statistics** | stale stats flip query plans (this caused a real 2-in-7 flake in Loop A) | `ANALYZE` after every seed |
| **Filesystem** | a leftover script or `SKILL.md` silently converts one arm into the other | the arm installer **deletes the other route** and asserts it is gone |
| **Answer file** | a stale `/output/finding.json` would be graded as this run's answer | removed before each run |

The database point is the one that would most easily go unnoticed: run the
script arm first and it warms the index counters, so the text arm's *correct*
answer changes. Same fixture, fresh database, every time.

---

## What is measured

### 1. Parity — graded first, and it gates everything

Both arms must reach the **same finding**. A route that is cheap because it
answers *worse* is not a saving, and reporting its token count as one would be
actively misleading.

Each arm writes `/output/finding.json`:

```json
{
  "redundant_indexes": ["tenant_id_1"],
  "reason": "prefix of tenant_id_1_status_1"
}
```

The verifier compares that against `expected-findings.yaml` — **structurally, no
judge**. The finding is a fact about the database, so it is checkable exactly.

### 2. Cost — reported only for runs that achieved parity

`tokens_fresh_input`, `tokens_output`, `ai_credits`, `agent_turns`, harvested
from the Copilot CLI session store by the same
[`harvest_metrics.py`](../documentdb-sdk-skills/shared/verifier/harvest_metrics.py)
the SDK-skills benchmark uses, so the two benchmarks cannot report cost
differently.

**The headline is cost conditional on parity.** Comparing tokens across runs
where one arm got the wrong answer compares nothing.

---

## Honest expectations

The script route should win on tokens — it is a compact JSON verdict rather than
raw output plus a skill file. What is genuinely unknown:

- whether the **saving survives caching** — the static proxy charged the text arm
  full price for a payload that is actually cached
- whether the text arm reaches **parity at all**, and how often. If it frequently
  gets the answer *wrong*, the story is about correctness, not tokens — a better
  story, and one `token-tests/` could not tell
- whether the script arm is ever *worse*, e.g. when a script emits a large report
  and the question needed one line

If the measured saving is far below 77%, that supersedes the old figure.
`token-tests/` stays in the tree, marked as the superseded estimate.

---

## Status

⬜ **Not yet run.** Building an agent-driven run needs model credentials
(`COPILOT_SDK_AUTH_TOKEN`); the harness, fixture, arms and parity grader are in
place and validated with scripted stand-ins. See [`results/`](results/).

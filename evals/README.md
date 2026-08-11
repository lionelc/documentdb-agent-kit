# `evals/` — Loop B: skill-efficacy evaluation

> **Two folders, two questions.** This repo tests two fundamentally different
> things, and conflating them is the mistake to avoid:
>
> | Folder | Loop | Question | Success looks like |
> |---|---|---|---|
> | [`../testing/`](../testing/) | **A — deterministic** | Do the **diagnostic scripts** return the *same* answer every time? | byte-identical `--json` across 3 runs |
> | **`evals/`** (here) | **B — non-deterministic** | Do the **text skills** make an agent produce *better* output, and at what cost? | higher quality / lower cost than a control run |
>
> Loop A is free, fast, and runs on every PR. Loop B costs AI credits and is run
> deliberately.

Loop B is built on **[Vally](https://aka.ms/vally)** (`@microsoft/vally-cli`,
MIT, pinned in [`package.json`](package.json)) — Microsoft's evaluation platform
for AI agents. Vally gives us, natively: multi-model runs, skills on/off
variants, an objective **`skill-invocation`** grader, real token/AI-credit
accounting from API `response.usage`, and LLM-judge graders for the cases where
nothing objective exists.

## Layout

```
evals/
├── package.json                  # pins @microsoft/vally-cli
├── documentdb-skills/
│   └── eval.yaml                 # stimuli + graders (the contract)
└── vally-results/                # run artifacts — gitignored, never committed
```

## Prerequisites

```bash
cd evals && npm install
export VALLY_TELEMETRY_OPTOUT=1 DO_NOT_TRACK=1   # see "Telemetry" below
```

**For real (non-mock) runs** the Copilot SDK executor needs an auth token in the
environment (`COPILOT_SDK_AUTH_TOKEN`); without it a run fails with
`Session was not created with authentication info or custom provider`.
Real runs consume AI credits.

## Running

```bash
npm run lint          # static validation — no agent, no cost
npm run eval:mock     # mock executor — free, but see the WARNING below
npm run eval          # real model — costs AI credits, needs auth

# filter by tag
npx vally eval -e documentdb-skills/eval.yaml --tag kind=anti-trigger
```

## ⚠️ The mock executor cannot score skill activation

`--executor mock` never invokes skills (`Skills used 0`). That means:

- **positive-trigger stimuli always FAIL on mock**, and
- **anti-trigger stimuli always PASS on mock — vacuously.**

So a green anti-trigger result on mock proves *nothing*, exactly like a
diagnostic script that "passes" determinism by finding nothing (see
[`../testing/scenarios/determinism/`](../testing/scenarios/determinism/)).

**Use mock only to validate the plumbing** — that the spec parses, skill paths
resolve, graders are wired. **Any real signal requires a real executor.**

## What Phase 1 covers

Skill **routing**: does the right skill activate for a given phrasing, and does
**no** DocumentDB skill activate for an unrelated question?

This was chosen deliberately as the first eval because it is:
- the **cheapest** useful signal,
- graded **objectively** (`skill-invocation` is binary — no LLM judge needed), and
- otherwise only ever verified by hand.

| Stimulus | Tag | Asserts |
|---|---|---|
| slow query on `db.orders` | `kind=trigger` | `documentdb-query-optimizer` **required** |
| array field + 30-day expiry | `kind=trigger` | `documentdb-indexing` **required** |
| pool exhaustion / timeouts | `kind=trigger` | `documentdb-connection` **required** |
| PostgreSQL partial index | `kind=anti-trigger` | **no** DocumentDB skill called |
| CSS centering | `kind=anti-trigger` | **no** DocumentDB skill called |

### Honest measurement: skills are never hinted

`environment.skills` makes the skills *discoverable* exactly as an installed user
would have them — the prompt **never tells the agent to use them**. This measures
the skill's **organic** effect rather than a hinted best case. (Protocol borrowed
from the MSBench `cosmos-sdk-skills` runner.)

## Grading policy — judge is the last resort

Prefer, in order:

1. deterministic / exact match → `../testing/` (Loop A)
2. **measured before/after delta** → apply the advice, re-measure (`run-command`)
3. structural assertion on the artifact → `program`, `file-matches`
4. semantic equivalence vs a golden output
5. **behavioural assertion** → `skill-invocation`, `tool-call`, `metric-threshold` ← *Phase 1 lives here*
6. contract conformance
7. LLM-as-a-judge → only for irreducibly subjective quality, blinded, cross-model panel, and always reported next to an objective score

A useful trick: convert 7 → 2/3 by **constraining the ask**. "Explain how to
speed this up" is judge-only prose; "emit the exact `createIndex(...)` you
recommend" is executable, so it can be applied and measured.

## Telemetry

Vally collects pseudonymous usage telemetry (including a persistent device
identifier) **by default**. Always export `VALLY_TELEMETRY_OPTOUT=1` /
`DO_NOT_TRACK=1` — the npm scripts assume you have.

## Next (not yet built)

- Real-model matrix: `claude-opus-5` × `gpt-5.6-sol` × `gemini-3.1-pro-preview`,
  skills vs control, `--runs 5` (`vally experiment` + `vally compare`)
- Before/after graders that apply a recommended index and re-measure `explain()`,
  paired with `index-redundancy-finder.sh --json` as an anti-gaming guard
- CI: Loop A every PR; Loop B on dispatch/schedule

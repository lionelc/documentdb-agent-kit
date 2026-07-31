# Scenario: KB Router Contract

> **Logic guard, not a DB test.** These tests exercise the knowledge-base router
> (`knowledge-base/kb_route.py` + `kb-route.sh`) which is a **pure text layer** —
> no DocumentDB container is required to route a query. They guard that natural-
> language questions resolve to the expected tool and that the scoring rules do
> not silently drift.

## Goal

The router maps a natural-language diagnostic question to the exact agent-kit
script (one hop). It is deterministic keyword/example scoring (stdlib only). This
scenario protects two things:

1. **Routing correctness** — a set of representative questions must resolve to the
   expected tool id (e.g. TOAST/large-document questions → `document-bloat-advisor`).
2. **Scoring transparency** — the additive rules that produce the score
   (`+3.0` multiword phrase, `+1.5` single keyword, `+2.5×` example overlap,
   `+2.0×` one-hop boost) stay intact, and confident routes clear the `>= 2.0`
   threshold.

It also runs the `kb-route.sh` wrapper end-to-end via subprocess to guard the
shell → `kb_route.py` seam (env-var handoff, valid `--json`).

## What the fixture plants

Nothing — the router reads `knowledge-base/kb.json` (the shipped KB). There is no
`fixture.js` and no seeded database.

## Contract

[`expected-findings.yaml`](expected-findings.yaml):
- `routes:` — a list of `{query, tool}` pairs the router must satisfy.
- `min_confident_score` — confident routes must score at least this.
- `phrase_case` — a query that must match a specific multiword keyword.

## Run

```bash
pytest scenarios/kb-router
```

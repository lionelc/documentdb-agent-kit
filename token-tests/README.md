# Token-Saving A/B Tests

Empirically measures the **context-token cost** of answering a DocumentDB
diagnostic question two ways, so the kit's "scripts save tokens" claim is a
*measured* number, not a marketing line.

- **Path A — text skill:** load the relevant `skills/<skill>/SKILL.md` into the
  model's context, then run the mongosh/psql commands that skill prescribes and
  feed their **raw output** back into context for the model to interpret.
- **Path B — KB router + script:** run `knowledge-base/kb-route.sh` (natural
  language → exact script; the router files are **executed, not loaded into
  context**) and feed the script's **compact answer** into context.

`tokens ≈ bytes / 4` (standard English/JSON BPE heuristic). Every payload is a
real byte count via `wc -c`; nothing is estimated except that 4-bytes/token
conversion and the multi-turn model (see Caveats).

## Files

| File | Role |
|------|------|
| `token-ab-measure.sh` | The harness. Emits a TSV, one row per (tool, dataset). Path-portable (derives the repo root from its own location). |
| `summarize.py` | Turns the harness TSV into a ratio / saving-rate table (`--md` for markdown). |
| `results-settled.tsv` | A captured snapshot (raw TSV). |
| `RESULTS.md` | The measured saving-rate table + per-tool summary (rendered results). |

## Prerequisites

- The `documentdb-local` container **Up**, with `DB_PASSWORD` exported and the
  demo databases seeded:
  ```bash
  export DB_PASSWORD='<your-password>'                                # the seeders/scripts require this
  bash ../scenarios/ecommerce/seed.sh                        # ecommerce
  bash ../scenarios/contoso/seed.sh                          # contoso (TOAST demo)
  bash ../scenarios/index-redundancy/seed.sh                 # idx_test (redundant indexes)
  ```
  If the container is stopped: `docker start documentdb-local`.
- `python3` + `bash` on the host. No other dependencies.

## Reproduce

From this directory (`token-tests/`):

```bash
# 1. run the A/B measurement (writes a TSV to stdout)
bash token-ab-measure.sh

# 2. run it and render the ratio / saving-rate table
bash token-ab-measure.sh | python3 summarize.py

# 3. markdown table (for a report/PR)
bash token-ab-measure.sh | python3 summarize.py --md

# 4. re-summarize the saved snapshot without re-measuring
python3 summarize.py < results-settled.tsv
```

Override defaults via env vars if your setup differs:

```bash
CONTAINER=my-docdb PORT=10260 PG_PORT=9712 DB_PASSWORD='<your-password>' \
  bash token-ab-measure.sh
```

## What the harness measures per tool

| Tool | Path A skill (commands it prescribes) | Path B (router + script) |
|------|----------------------------------------|--------------------------|
| `document-bloat-advisor` | `query-optimizer`: getIndexes + stats + $indexStats + explain + findOne | `document-bloat-advisor.sh --json` |
| `index-redundancy-finder` | `indexing`: per-collection getIndexes + $indexStats | `index-redundancy-finder.sh --json` |
| `perf-advisor` | `query-optimizer` workflow | `perf-advisor.sh --json` |
| `data-integrity-check` | `data-modeling`: $lookup orphan probes + findOne | `data-integrity-check.sh --json` |
| `db-config-advisor` | `storage` (no local commands) → agent improvises psql | `db-config-advisor.sh --json` |

`ratio = A_tok / B_tok`  ·  `saving = (A_tok − B_tok) / A_tok`.

## Latest verified result

See [`RESULTS.md`](RESULTS.md) for the full measured table (9 tool×dataset pairs,
single-pass token saving **52%–97%, median 77%**) and per-tool summary. Raw data in
[`results-settled.tsv`](results-settled.tsv). Regenerate anytime with
`bash token-ab-measure.sh | python3 summarize.py`.

## Reproducibility caveats (read before comparing runs)

1. **`index-redundancy-finder` output is workload-volatile.** Its `UNUSED_VERIFIED`
   findings depend on PostgreSQL index-usage stats. **Right after a container
   restart** every `idx_scan = 0`, so *all* secondary indexes are flagged unused
   → a big Path B report → saving drops to ~2×. Once queries exercise the indexes
   (or on a warm instance), that output shrinks → ~13.8×. Its *structural*
   findings (prefix/duplicate) are stable; the *unused-index* ones are not. Treat
   its saving as a **range (52–93%)**, and warm the DB before measuring for a
   stable number. The `idx_test` row (2.1×) is the "many real findings" worst case.
2. **More findings ⇒ larger Path B output ⇒ lower saving** — but Path B still wins
   in every case, and a richer diagnosis is the point, not waste.
3. **Path A skill size feeds the ratio.** Growing a `SKILL.md` raises Path A and
   thus the measured saving. (E.g. `data-modeling` grew when the large-field-split
   rule was added, nudging `data-integrity` saving up.)
4. **Single-pass payloads.** These are one-shot context sizes. **Multi-turn is
   larger**: a text skill is re-sent on every turn, so end-to-end savings widen
   (~8× modeled in the cross-tool report). The router path stays 2–3 lean turns.
5. **Path A is a faithful reconstruction**, not two live agent runs — the payload
   bytes are real; the turn model is an estimate. For an exact end-to-end figure,
   run the same prompt both ways and diff `usage_input_tokens` per turn from the
   Copilot session store.

## Related

- Measured results: [`RESULTS.md`](RESULTS.md).
- The router being measured: [`../knowledge-base/`](../knowledge-base/) (`kb.json`, `kb-route.sh`, `kb_route.py`).
- The diagnostic scripts being measured: [`../scripts/`](../scripts/).

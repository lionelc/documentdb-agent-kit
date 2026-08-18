# Token-Saving Results

> ## Scope: this measures CONTEXT PAYLOAD, not end-to-end cost
>
> Every number below is a real `wc -c` byte count of real command output,
> converted with `tokens ≈ bytes / 4`. **No model is called**, so these are not
> measured consumption and there is no check that either path reaches the
> correct answer.
>
> **That does not make the comparison unfair.** The obvious objection — that
> `bytes/4` is a rule of thumb and JSON tokenises differently from prose — was
> tested against a real tokeniser (`o200k_base`) on the actual payloads:
>
> | | `bytes/4` | real tokeniser |
> |---|---|---|
> | Path A total | 3,063 tok | 3,327 tok |
> | Path B total | 551 tok | 613 tok |
> | **ratio** | **5.56×** | **5.43×** |
> | **saving** | **82.0%** | **81.6%** |
>
> Per file the proxy is off by up to 33%, but the errors **largely cancel in
> the ratio** because both paths mix prose and structured output. The ratio
> error is **+2.4%**. Re-check any time with
> [`validate-proxy.py`](validate-proxy.py).
>
> So the saving rates below are sound **for what they measure**: how much
> context each route puts in front of a model, in a single pass.
>
> **What they cannot tell you**, and what
> [`benchmarks/documentdb-route-efficiency/`](../benchmarks/documentdb-route-efficiency/README.md)
> is built to measure instead:
>
> - **Multi-turn cost.** A `SKILL.md` is sent once then served from cache at
>   ~10% of the rate; the text route may also need several turns, each
>   re-sending context. These pull in opposite directions and neither is
>   visible here.
> - **Output and reasoning tokens**, which are billed and not counted here.
> - **Correctness.** A route that is cheaper because it answers *worse* has
>   saved nothing. Nothing below checks that.
>
> The two are complementary, not competing: this is the cheap, credential-free
> payload bound; that one is the measured end-to-end cost, gated on parity.
Measured token cost of answering the same DocumentDB diagnostic question two
ways (see [`README.md`](README.md) for the full methodology):

- **Path A — text skill:** load the relevant `SKILL.md` into context, then run the
  mongosh/psql commands it prescribes and feed the **raw output** back to the model.
- **Path B — KB router + script:** `kb-route.sh` (executed, not loaded) → the exact
  script → its **compact answer** into context.

`tokens ≈ bytes / 4`. `ratio = A_tok / B_tok`; `saving = (A_tok − B_tok) / A_tok`.
Every payload is a real `wc -c` byte count.

## Result (quickstart datasets: `contoso`, `ecommerce`, `idx_test`)

| Tool | Dataset | Path A tok | Path B tok | Ratio | Saving |
|---|---|--:|--:|--:|--:|
| document-bloat-advisor | contoso | 4,732 | 267 | 17.7× | 94.4% |
| document-bloat-advisor | ecommerce | 3,793 | 127 | 29.9× | 96.7% |
| index-redundancy-finder | ecommerce | 2,750 | 200 | 13.8× | 92.7% |
| index-redundancy-finder | idx_test | 1,725 | 834 | 2.1× | 51.7% |
| perf-advisor | contoso | 4,732 | 1,448 | 3.3× | 69.4% |
| perf-advisor | ecommerce | 3,792 | 1,480 | 2.6× | 61.0% |
| data-integrity-check | contoso | 2,213 | 233 | 9.5× | 89.5% |
| data-integrity-check | ecommerce | 682 | 156 | 4.4× | 77.1% |
| db-config-advisor | contoso | 1,072 | 244 | 4.4× | 77.2% |

**9 (tool, dataset) pairs · single-pass token saving 52%–97% · median 77%.**

Raw data: [`results-settled.tsv`](results-settled.tsv). Reproduce with
`bash token-ab-measure.sh | python3 summarize.py`.

## Per-tool summary

| Tool | Saving | Note |
|---|--:|---|
| document-bloat-advisor | **94–97%** | most stable; tiny JSON verdict |
| index-redundancy-finder | **52–93%** | volatile: depends on #findings + index-usage stats |
| data-integrity-check | **77–90%** | scales with #orphans / type issues |
| db-config-advisor | **~77%** | single dataset measured |
| perf-advisor | **61–69%** | larger JSON (full multi-check report) |

## Why Path B wins (beyond token count)

- The router files (`kb.json`, `kb-route.sh`, `kb_route.py`) are **executed, not
  loaded into context** — they cost the model **0 tokens**.
- The scripts return a **compact structured verdict** instead of raw
  `getIndexes`/`stats`/`explain`/`findOne` dumps.
- **Multi-turn widens the gap:** a text skill is re-sent on every turn, while the
  router path stays 2–3 lean turns (≈8× end-to-end, modeled).
- **Correctness:** for TOAST (`document-bloat`) and cache (`db-config`), the root
  cause is a PostgreSQL storage effect a Mongo-layer skill can't reach; the scripts
  do the cross-layer analysis deterministically.

## Caveats

- **Single-pass payloads** (`bytes/4`); treat token columns as ±20%.
- **`index-redundancy-finder` is workload-volatile** — its `UNUSED_VERIFIED`
  findings depend on PostgreSQL index-usage stats. Right after a container restart
  every index looks unused → larger output → lower saving (~2×); warm it and the
  saving rises (~13.8×). Its `idx_test` row is the "many real findings" worst case.
- **More findings ⇒ bigger Path B output ⇒ lower saving** — but Path B still wins
  everywhere, and a richer diagnosis is the point.
- **Path A is a faithful reconstruction** of the skill-guided commands, not two live
  agent runs; payload bytes are real, the multi-turn model is an estimate. For an
  exact end-to-end figure, run the same prompt both ways and diff
  `usage_input_tokens` per turn from the agent session store.

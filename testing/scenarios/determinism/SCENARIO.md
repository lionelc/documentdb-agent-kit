# Scenario: Determinism (Loop A)

> **The deterministic half of the kit's testing.** The diagnostic scripts are
> *tools*, not agents: given the same database state they must return the same
> answer every time. This scenario proves that, and fails loudly when they don't.

## Goal

For every diagnostic script, run it **3 times** against one untouched database
and assert the `--json` results are identical after canonicalisation.

Determinism is asserted on `--json` only. The human-readable output deliberately
embeds a wall-clock banner (`Timestamp: …`) and measured latencies, so it is not
byte-stable and is not part of this contract.

## What the fixture plants

[`fixture.js`](fixture.js) seeds `test_determinism` so **every** script produces
non-empty output — otherwise the assertion would be vacuous (see below):

| Collection | Plants | Exercises |
|---|---|---|
| `accounts` | prefix-redundant + duplicate indexes | `index-redundancy-finder.sh` |
| `invoices` | orphaned `account_id` refs, mixed-type `amount` | `data-integrity-check.sh` |
| `articles` | ~6 KB of **incompressible** text per doc | `document-bloat-advisor.sh` |
| `events` | no secondary indexes | `perf-advisor.sh` |
| — | (PG config/cache always reported) | `db-config-advisor.sh` |

Two fixture details that matter:

- **The fixture is itself reproducible.** It uses a fixed-seed Lehmer LCG, never
  `Math.random()` — a determinism scenario cannot be seeded non-deterministically.
- **The large text is incompressible.** PostgreSQL compresses (pglz) before
  storing out of line, so repeated filler text shrinks away and never TOASTs.
  Random-ish characters really do land in TOAST, which is what the bloat advisor
  looks for.

## The three traps this suite avoids

1. **False determinism.** A script that finds *nothing* returns the same empty
   result every run — which proves nothing. `must_find` asserts each script
   actually reported something.
2. **Over-broad normalisation.** The volatile allowlist is small, **measured**
   (not guessed), and documented with the observed drift that justifies each
   entry. Drift outside it fails the test.
3. **A test that cannot fail.** `test_injected_drift_is_detected` is a negative
   control. Verified end-to-end by temporarily emitting `$RANDOM` from
   `db-config-advisor.sh` — the suite failed, as it must.

## Contract

[`expected-findings.yaml`](expected-findings.yaml):

| Key | Meaning |
|---|---|
| `runs` | how many times each script is run (3) |
| `scripts[].must_find` | output must be non-empty (anti-false-determinism) |
| `volatile_fields` | live measurements removed before comparison |
| `order_insensitive_lists` | lists sorted by a volatile metric, so order-normalised |
| `sampled_count_maps` | `{category: count}` maps from `$sample` — counts blanked, categories kept |
| `sampled_size_strings` | summary strings with sampled byte sizes — sizes blanked, field ranking kept |

## Findings this suite produced on its first run

It immediately caught **two real sampling nondeterminisms** — both now documented
in `expected-findings.yaml` with a follow-up, not silently normalised away:

1. **`data-integrity-check.sh`** uses `$sample` for type-consistency, so counts
   wobble: `{"number": 87, "string": 13}` vs `{"number": 85, "string": 15}`.
   The *finding* (`amount` holds both numbers and strings) is stable and is still
   asserted; only the sampled counts are blanked.
2. **`document-bloat-advisor.sh`** derives `dominant_fields` from a sample, so
   average field sizes wobble (`title:13B` vs `title:12B`). The field **ranking**
   — and therefore `recommended_split_field` — is stable and still asserted.

3. **`perf-advisor.sh`** builds `slow_queries` by *timing* queries against a
   threshold — so it is not only the `ms` value that moves, but **which queries
   qualify**. It passed in isolation and failed inside the full test run, where
   cache warmth and load differ. The list and its summary count are treated as
   volatile; perf-advisor's *structural* findings (collections, `index_health`,
   `collscans`) are still asserted.

**Follow-up (open):** make both samplers deterministic (e.g. order by `_id` and
take the first N) so the counts stabilise too. `slow_queries` is inherently
timing-based and will likely always be volatile — that is a property of the
measurement, not a bug.

## Run

```bash
export DB_PASSWORD='<your-password>'
cd testing && pytest scenarios/determinism
```

Requires a running `documentdb-local` container (see the repo README).

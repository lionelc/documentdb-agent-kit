# Scenario: JSON Output Contract (all diagnostic scripts)

> **Shape guard, not a findings guard.** This scenario asserts the *structure*
> and *validity* of every script's `--json` output — never specific finding
> counts. It is deliberately dataset-agnostic.

## Goal

Every diagnostic script exposes a `--json` mode so the knowledge-base router / an
agent can consume a compact machine-readable result instead of the full human
report. This scenario guards two regressions that are invisible to the existing
human-text contract tests and that actually occurred during development:

1. **Invalid JSON** — a stray brace or a partial value making `json.loads` fail.
2. **Non-JSON leakage on stdout** — box-drawing headers, `SET` command tags from
   psql, or any debug line contaminating the `--json` stream.

## What the fixture plants

A small, generic multi-collection database (`test_json_contract`) with enough
shape for every script to produce a fully-populated result:

- `customers` / `orders` — a foreign-key relationship (`orders.customer_id`) and a
  prefix-redundant index pair on `orders`.
- `documents` — rows carrying a large **varied** (low-compressibility) text field
  so it lands in PostgreSQL TOAST (exercises the large-document advisor).

## Contract

[`expected-findings.yaml`](expected-findings.yaml) declares, per script, the
expected top-level JSON `type` (`list` or `object`) and required `keys`. The test
also asserts the nested shape of the two richest payloads (`perf-advisor`,
`data-integrity-check`) and that `--json` stdout is pure JSON.

## Run

```bash
pytest scenarios/json-contract
```

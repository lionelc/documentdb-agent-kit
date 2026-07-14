# Scenario: E-Commerce — Redundant Indexes

> **Fixed scenario.** Do not edit `fixture.js` or `expected-findings.yaml` to
> make a failing test pass. Edit only when intentionally changing what the
> scenario plants.

## Goal

Guard `index-redundancy-finder.sh` against regression: given an e-commerce
database with **intentionally redundant indexes**, the tool must detect every
planted redundancy and must **not** flag the good ("keep") indexes.

## What the fixture plants

| Collection | Index | Expected finding |
|-----------|-------|------------------|
| customers | `{tenant_id}` | PREFIX_REDUNDANT (prefix of `{tenant_id,status}`) |
| customers | `{email}` | EXACT_DUPLICATE (shadowed by unique `{email}`) |
| orders | `{customer_id}` | PREFIX_REDUNDANT |
| orders | `{customer_id,status}` | PREFIX_REDUNDANT |
| orders | `{region,created_at:1}` + `{region,created_at:-1}` | REVERSE_VARIANT |
| sessions | `{ip_address}`, `{user_agent}` | unused + write cost (UNUSED_VERIFIED / WRITE_TAX) |

KEEP indexes (`{tenant_id,status}`, unique `{email}`,
`{customer_id,status,created_at:-1}`) receive query traffic so they show real
reads and must never be flagged as structurally redundant.

## Contract

See [`expected-findings.yaml`](expected-findings.yaml).

## Run

```bash
pytest scenarios/ecommerce-redundant-indexes
```

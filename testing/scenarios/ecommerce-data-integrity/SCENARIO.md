# Scenario: E-Commerce — Data Integrity (hard-logic only)

> **Fixed scenario.** Do not edit the fixture or contract to make a failing
> test pass.

## Goal

Guard `data-integrity-check.sh` against regression. The checker performs **only
hard structural integrity checks** — no business-semantic guessing — so this
scenario plants the two structural defects it must catch.

## What the fixture plants

| Defect | Detail | Check |
|--------|--------|-------|
| ORPHAN FK | ~10% of `orders.customer_id` reference non-existent customers | Referential integrity |
| TYPE INCONSISTENCY | `signups.ref_code` is a number in some docs, a string in others | Type consistency |

## Deliberately NOT planted

Duplicate values, negative amounts, empty/required fields, out-of-range values —
these are **business rules, not structural integrity**, and the checker no
longer guesses them from field names. Enforce those with a `$jsonSchema`
validator or a unique index instead.

## Contract

See [`expected-findings.yaml`](expected-findings.yaml). The script has no
`--json`, so the test matches stable text markers (`ORPHAN FK`,
`"<field>" has mixed types`, `Total ... issues: N`) and also asserts the removed
soft checks are absent.

## Run

```bash
pytest scenarios/ecommerce-data-integrity
```

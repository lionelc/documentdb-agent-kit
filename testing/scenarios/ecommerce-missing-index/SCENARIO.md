# Scenario: E-Commerce — Missing Index

> **Fixed scenario.** Do not edit the fixture or contract to make a failing
> test pass.

## Goal

Guard `perf-advisor.sh`'s collection-scan audit against regression: an
unindexed collection queried on its fields must be flagged, while a properly
indexed collection must stay clean (no false positives).

## What the fixture plants

| Collection | Indexes | Expectation |
|-----------|---------|-------------|
| events | none (only `_id_`) | every field query is a full scan → flagged |
| products | `{sku}`, `{category}`, `{price}` | all queried fields covered → clean |

## DocumentDB note

DocumentDB is Postgres-backed and **never emits a MongoDB `COLLSCAN` stage** —
an unindexed filter falls back to a full `IXSCAN` over the `_id_` primary key.
`perf-advisor.sh` therefore flags a missing index when a query resolves to
`_id_`/`COLLSCAN` **and** no index covers the filtered field. (A small
collection may resolve to `_id_` even when an index exists, because the cost
optimizer prefers the PK scan — that is not a missing index and is not flagged.)

## Contract

See [`expected-findings.yaml`](expected-findings.yaml).

## Run

```bash
pytest scenarios/ecommerce-missing-index
```

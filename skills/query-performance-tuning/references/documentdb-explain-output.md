# Reading Azure DocumentDB `explain("executionStats")`

> Reference doc for the `documentdb-query-performance-tuning` skill. Load this
> when you need to interpret a **real** Azure DocumentDB explain plan.
>
> Azure DocumentDB's query planner is **PostgreSQL-backed**, so
> `explain("executionStats")` emits `"explainVersion": 2` output that carries
> **planner cost estimates** and **runtime buffer stats** you will not see in
> community MongoDB. Learn these fields — the MongoDB-standard summary is not
> enough to read a real DocumentDB plan.
>
> Source: [How to read explain output](https://learn.microsoft.com/en-us/azure/documentdb/how-to-read-explain-output),
> [Query Performance Tuning Guide](https://devblogs.microsoft.com/documentdb/query-performance-tuning-guide/)

## DocumentDB-specific fields (not in community MongoDB)

| Field | Where | What it means |
|---|---|---|
| `PARALLEL_SORT_MERGE` | winning-plan `stage` | Top stage that merges results from parallel workers (`workersPlanned` / `parallelWorkers`). Its own `totalDocsExamined` is the **merged** count and can look tiny — always drill into `inputStage`. |
| `startupCost` / `totalCost` | every stage | PostgreSQL planner cost estimate (not milliseconds). A huge `totalCost` on a `COLLSCAN` (e.g. `34418`) is a red flag even when wall-clock looks OK. |
| `estimatedTotalKeysExamined` | queryPlanner stages | Planner **estimate** of keys examined. Compare against the **actual** `totalKeysExamined` in `executionStats`. |
| `runtimeFilterSet` / `totalDocsRemovedByRuntimeFilter` | `COLLSCAN` | Filters applied *while scanning*. A large `totalDocsRemovedByRuntimeFilter` means the scan read and threw away almost everything. |
| `numBlocksFromCache` | execution stages | Buffer-cache blocks touched. A large value on a scan stage signals heavy page churn. |
| `indexUsage.scanLoops` | `IXSCAN` | Number of index key lookups performed. |
| `indexUsage.scanType` | `IXSCAN` | `"regular"` = scan without an ordering guarantee (an in-memory `SORT` may follow); `"ordered"` = index walked **in sort order** (no in-memory sort). |
| `indexUsage.scanKeys[].estimatedEntryCount` | `IXSCAN` | Estimated matching entries per key; `isInequality` flags a range bound. |
| `hasOrderBy` / `bounds` / `indexFilterSet` / `direction` | `IXSCAN` | `hasOrderBy: true` + a `direction` means the sort is served by the index. `bounds` shows the exact scanned key range. |
| `indexCosts[]` | queryPlanner | Per-candidate-index costing: `selectivity`, `correlation`, `estimatedPercentIndexPagesLoaded`, `estimatedTotalIndexEntries`, `boundarySelectivity`. |

## Gotcha: the top-line numbers lie

The **top stage** of a plan reports post-merge / post-sort counts, so
`totalDocsExamined` and `executionTimeMillis` at the top can look *great* even
during a full scan. You must drill into the nested `inputStage` chain down to the
`COLLSCAN` / `IXSCAN` to see the real work. In the worked example the top
`PARALLEL_SORT_MERGE` reports `totalDocsExamined: 18`, but the underlying
`COLLSCAN` reports `totalDocsExamined: 333333`.

## The three plans, annotated

### 1. `COLLSCAN` — no index (bad)

```json
"winningPlan": {
  "stage": "PARALLEL_SORT_MERGE",
  "totalCost": 40692.13,
  "inputStage": {
    "stage": "SORT",
    "sortKey": [ { "createdAt": -1 } ],
    "inputStage": {
      "stage": "COLLSCAN",
      "totalCost": 34418.4,
      "runtimeFilterSet": [ { "status": { "$eq": "shipped" } }, ... ]
    }
  }
}
```
```json
"executionStats": {
  "executionStages": {
    "inputStage": {                       // drill down to the COLLSCAN
      "inputStage": {
        "stage": "COLLSCAN",
        "totalDocsExamined": 333333,
        "totalDocsRemovedByRuntimeFilter": 333327,
        "numBlocksFromCache": 25000
      }
    }
  }
}
```
Signals: `COLLSCAN` stage, huge `totalCost`, huge `totalDocsExamined` /
`totalDocsRemovedByRuntimeFilter` at the scan stage, blocking `SORT` above it.

### 2. Naive single-field `IXSCAN` (better, still wrong)

```json
"inputStage": {
  "stage": "IXSCAN",
  "indexName": "status_1",
  "nReturned": 249800,
  "totalKeysExamined": 249800,
  "indexUsage": { "scanLoops": 249800, "scanType": "regular" }
}
```
Signals: `IXSCAN` now, but `totalKeysExamined` is still enormous vs `nReturned`,
`scanType: "regular"` (not `"ordered"`), and a `SORT` stage still sits above it.

### 3. ESR compound `IXSCAN` (good)

```json
"winningPlan": {
  "stage": "FETCH",
  "inputStage": {
    "stage": "IXSCAN",
    "indexName": "customerId_1_status_1_createdAt_-1",
    "direction": "Forward",
    "hasOrderBy": true,
    "indexUsage": { "scanLoops": 19, "scanType": "ordered" }
  }
},
"executionStats": {
  "nReturned": 18,
  "totalKeysExamined": 18,
  "executionTimeMillis": 0.058
}
```
Signals: no `SORT` stage, `scanType: "ordered"`, `hasOrderBy: true`,
`totalKeysExamined ≈ nReturned`. A **covered** query removes even the `FETCH`,
leaving a bare `IXSCAN`.

## What "good" looks like

| Metric | Good | Bad |
|---|---|---|
| Scan-stage `stage` | `IXSCAN` | `COLLSCAN` |
| `totalKeysExamined / nReturned` | ≈ 1 | ≫ 1 (poor selectivity) |
| `totalDocsExamined / nReturned` (scan stage) | ≈ 1 | ≫ 1 (scanning too much) |
| `indexUsage.scanType` | `ordered` (when sorting) | `regular` + a `SORT` stage |
| `SORT` stage present | absent | present (blocking in-memory sort) |
| `FETCH` stage present | absent = covered query | present (unavoidable if you need the full doc) |

## References

- [How to read explain output](https://learn.microsoft.com/en-us/azure/documentdb/how-to-read-explain-output)
- [Query Performance Tuning Guide](https://devblogs.microsoft.com/documentdb/query-performance-tuning-guide/) (devblog)
- Companion: [`../../query-optimizer/references/core-indexing-principles.md`](../../query-optimizer/references/core-indexing-principles.md) · [`../../indexing/index-compound-esr.md`](../../indexing/index-compound-esr.md)

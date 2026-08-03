# Query-Performance Skill Test — Instruction & Results

> **Generated:** 2026-07-30 18:04:41 UTC · **Re-run (post-merge):** 2026-07-30 21:18 UTC — identical scan-work results; test 4.1 re-labeled to `documentdb-query-optimizer` after the `query-optimization` merge · **Status:** Public Preview (see repo `AGENTS.md`)
> **Article under test:** [Query Performance Tuning Guide](https://devblogs.microsoft.com/documentdb/query-performance-tuning-guide/) (Azure DocumentDB devblog)
> **Skills exercised:** `documentdb-query-performance-tuning`, `documentdb-query-optimizer` (two facets: index recommendation + explain-plan verification, the latter merged from the former `documentdb-query-optimization`), `documentdb-indexing` (`index-compound-esr`)

This document is a **reproducible before/after test** that validates the query-performance
skills against a **real local DocumentDB container**. It takes a realistic slow query per case,
captures `explain("executionStats")` **before** any supporting index (the `COLLSCAN` baseline),
applies the index that skill recommends, and re-captures explain **after**. Every number below is
measured, not estimated. The 2026-07-30 21:18 UTC re-run (after `query-optimization` was merged
into `query-optimizer`) reproduced every scan-work figure exactly.

**Reproducible test artifacts** (added with this doc):
- `scenarios/ecommerce/query-perf-skill-test.js` — the mongosh measurement harness
- `scenarios/ecommerce/query-perf-skill-test.sh` — the container runner

> ### ⚠️ Key caveat (read first)
> The **headline optimization reproduces** here: every skill turns a 50,000-doc `COLLSCAN`
> into a selective `IXSCAN`. But two of the article's *further* optimizations — **index-backed
> sort** (removing the in-memory `SORT`) and **covered queries** (removing the `FETCH`) — **do
> not reproduce on the `documentdb-local` image**, because the experimental engine flags that
> enable them ship **off** and are **pinned per-session by the gateway** (so even `ALTER SYSTEM`
> can't flip them). These are managed **Azure DocumentDB** behaviors, per the article. Full,
> verified detail and the fuller list of gated flags is in [§6 Caveats](#6-honest-caveats-local-image-vs-managed-azure-documentdb).

---

## 1. Is the `scenarios/` dataset a good fit? — Yes: `ecommerce`

The existing **`ecommerce`** seed (`scenarios/ecommerce/seed.sh`) is an excellent match for the
article. Its `orders` collection is seeded with **50,000 documents and *no* secondary index**
(only the default `_id`), so the "before" state is a genuine full collection scan — exactly the
article's starting point. The document shape maps almost 1:1 onto the article's example:

| Article field | `ecommerce.orders` field | Notes |
|---|---|---|
| `status: "shipped"` | `status` ∈ {pending, confirmed, shipped, delivered, cancelled} | `"shipped"` ≈ 10,127 / 50,000 docs (low cardinality) |
| `customerId: "C-4821"` | `customer_id` = `CUST_000000`…`CUST_004999` | 5,000 distinct → **high cardinality** (~10 orders each), like the article's customerId |
| `createdAt` | `created_at` (all in 2024) | supports the `$gte: ISODate("2024-01-01")` range + sort |
| (order total) | `total_amount` | used for the range-predicate (ESR) case |
| (city) | `shipping_city` ∈ 10 cities | used for the two-equality case |

The only differences from the article are **field naming** (`customer_id`/`created_at` vs
`customerId`/`createdAt`) and **scale** (50K docs vs the article's 1M). The before/after story
is identical.

> The other datasets are **not** a fit for this article: `contoso` targets large-text/TOAST
> bloat and `index-redundancy` targets duplicate/unused indexes — different diagnostics.

---

## 2. Environment & prerequisites

| Item | Value |
|---|---|
| Container image | `ghcr.io/microsoft/documentdb/documentdb-local@sha256:0fcf634531c1917ad0855ff9f4354aca0a5c5d8e435f08250568deb37eeb0ad5` |
| Container name | `documentdb-local` |
| Gateway (Mongo API) | container-internal `localhost:10260`, TLS, SCRAM-SHA-256 |
| PostgreSQL engine | container-internal `localhost:9712` |
| Credentials | user `docdbadmin`, password `Test1234` (`DB_PASSWORD`) |
| mongosh client | `2.3.8` |

> **Reproducibility gotcha:** this `documentdb-local` image **does not bundle a `mongosh`
> client**, but `scenarios/*/seed.sh` and the harness invoke `mongosh` via `docker exec`. Install
> it into the container once (root):
> ```bash
> docker exec -u root documentdb-local bash -lc '
>   cd /tmp && wget -q https://downloads.mongodb.com/compass/mongosh-2.3.8-linux-x64.tgz -O m.tgz &&
>   tar xzf m.tgz && cp mongosh-2.3.8-linux-x64/bin/mongosh /usr/local/bin/ &&
>   cp mongosh-2.3.8-linux-x64/bin/mongosh_crypt_v1.so /usr/local/lib/ 2>/dev/null; mongosh --version'
> ```

### Bring up + seed

```bash
# 1. start the container (host ports optional; seeders use docker exec)
docker run -d --name documentdb-local -e USERNAME=docdbadmin -e PASSWORD=Test1234 \
  ghcr.io/microsoft/documentdb/documentdb-local:latest
# 2. install mongosh into the container (see gotcha above)
# 3. seed the ecommerce dataset (~50K orders; takes ~1 min)
export DB_PASSWORD=Test1234
bash scenarios/ecommerce/seed.sh
```

---

## 3. How each skill is triggered (exact query words)

All trigger phrases resolve **deterministically** in the router's skill space (Route B).

> **Post-run update:** since this test was generated, the former `documentdb-query-optimization`
> rule skill was **merged into `documentdb-query-optimizer`** (its explain-verification content now
> lives in `query-optimizer/references/query-explain-plan.md`). So test 4.1 below is now the
> *explain-plan verification* facet of `query-optimizer`, and its trigger routes to `query-optimizer`.

| Skill | Type | Exact trigger phrase | `kb-route.sh` result (verified) |
|---|---|---|---|
| `documentdb-query-optimizer` (explain-plan verification) | standalone | "use explain to check whether this query uses an index or does a collection scan" | → skill **`query-optimizer`** (7.10) ✅ |
| `documentdb-query-optimizer` | standalone | "optimize this query and recommend an index" | → skill **`query-optimizer`** (9.00) ✅ |
| `documentdb-query-performance-tuning` | standalone | "how do I read the explain output and apply the ESR rule to tune this query" | → skill **`query-performance-tuning`** (11.38) ✅ |
| `documentdb-indexing` (`index-compound-esr`) | rule-folder | "which compound index should I design for this filter, sort, and range query" | → skill **`indexing`** (7.50) ✅ |

Try any phrase yourself:
```bash
bash knowledge-base/kb-route.sh --json "optimize this query and recommend an index"
```

---

## 4. Before/after results (measured)

**How to read these.** Azure DocumentDB's planner is PostgreSQL-backed, so the **top-line**
`totalDocsExamined` is a *post-sort* count and can look tiny even during a full scan — the
article warns about exactly this. The honest "work" metric is **documents/keys examined at the
scan stage**, which the harness drills down to. `executionTimeMillis` is the **min of 5 runs**
but is noisy at this data size (see caveats).

Each test runs against `ecommerce.orders` (50,000 docs). "Scan work" = docs examined by a
`COLLSCAN` vs keys examined by the `IXSCAN`.

### 4.1 `documentdb-query-optimizer` (explain-plan verification, merged from `query-optimization`)

**Goal:** explain() literacy — a `COLLSCAN` becomes an `IXSCAN` once an index supports the filter.

```javascript
db.orders.find({ order_id: "ORD_012345" })                    // single high-selectivity equality
db.orders.createIndex({ order_id: 1 })                        // the fix
```

| Metric | Before | After |
|---|---|---|
| Scan stage | **COLLSCAN** | **IXSCAN** (`order_id_1`) → FETCH |
| Examined at scan | **50,000 docs** | **1 key** |
| Blocking SORT | – | – |
| nReturned | 1 | 1 |
| `executionTimeMillis` (min/5) | 9 ms | 0 ms |
| Top-line `totalDocsExamined` | 50,000 | 1 |

**Scan work: 50,000 → 1 (≈50,000× fewer).** The cleanest case: no sort, so the plan collapses to
a bare index lookup + fetch.

### 4.2 `documentdb-query-optimizer` — recommend a compound index

**Goal:** recommend a compound index for a specific slow query (two equality fields + sort).

```javascript
db.orders.find({ status: "shipped", shipping_city: "Seattle" }).sort({ created_at: -1 })
db.orders.createIndex({ status: 1, shipping_city: 1, created_at: -1 })   // ESR: 2 equality, then sort
```

| Metric | Before | After |
|---|---|---|
| Scan stage | **COLLSCAN** | **IXSCAN** (`status_1_shipping_city_1_created_at_-1`) → FETCH |
| Examined at scan | **50,000 docs** | **998 keys** |
| Blocking SORT | yes | yes¹ |
| nReturned | 998 | 998 |
| `executionTimeMillis` (min/5) | 14 ms | 3 ms |

**Scan work: 50,000 → 998 (≈50× fewer).** ¹The blocking `SORT` persists on this local image — see
caveat §6.1.

### 4.3 `documentdb-query-performance-tuning` — the article's flagship query (ESR + covered)

**Goal:** full ESR compound index with the **most-selective equality first**, plus the
covered-query variant.

```javascript
db.orders.find({
  status: "shipped",
  customer_id: "CUST_004087",
  created_at: { $gte: ISODate("2024-01-01") }
}).sort({ created_at: -1 })
db.orders.createIndex({ customer_id: 1, status: 1, created_at: -1 })   // customer_id first = most selective
// covered variant adds projection { _id:0, customer_id:1, status:1, created_at:1 }
```

| Metric | Before | After | After (covered) |
|---|---|---|---|
| Scan stage | **COLLSCAN** | **IXSCAN** → FETCH | **IXSCAN** → FETCH² |
| Examined at scan | **50,000 docs** | **10 keys** | **10 keys** |
| Blocking SORT | yes | yes¹ | yes¹ |
| nReturned | 10 | 10 | 10 |
| `executionTimeMillis` (min/5) | 12 ms | 28 ms³ | 28 ms³ |

**Scan work: 50,000 → 10 (≈5,000× fewer).** Putting the high-cardinality `customer_id` first is
why this drops to 10 keys while §4.2 (leading with low-cardinality `status`) only drops to 998 —
a direct demonstration of the article's *"most selective field first"* rule.
²The covered projection does **not** remove the `FETCH` on this local image (caveat §6.1).
³Wall-clock is noisy on a 10-row result (caveat §6.2); the scan-work reduction is the real signal.

### 4.4 `documentdb-indexing` — `index-compound-esr` (Range LAST)

**Goal:** ESR with a range predicate — Equality, then Sort, then **Range last**.

```javascript
db.orders.find({ status: "shipped", total_amount: { $gt: 500 } }).sort({ created_at: -1 })
db.orders.createIndex({ status: 1, created_at: -1, total_amount: 1 })   // E → S → R
```

| Metric | Before | After |
|---|---|---|
| Scan stage | **COLLSCAN** | **IXSCAN** (`status_1_created_at_-1_total_amount_1`) → FETCH |
| Examined at scan | **50,000 docs** | **8,899 keys** |
| Blocking SORT | yes | yes¹ |
| nReturned | 8,899 | 8,899 |
| `executionTimeMillis` (min/5) | 24 ms | 42 ms³ |

**Scan work: 50,000 → 8,899 (≈5.6× fewer).** The modest reduction is expected and instructive:
`status: "shipped"` + `total_amount > 500` is a **low-selectivity** predicate (most shipped
orders exceed \$500), so even a correct ESR index cannot narrow much. Selectivity, not index
correctness alone, bounds the win.

---

## 5. Summary

| Skill | Query shape | Recommended index | Scan work (before → after) | Reduction |
|---|---|---|---|---|
| `query-optimizer` (explain verification) | 1 equality, no sort | `{order_id:1}` | 50,000 → 1 | **≈50,000×** |
| `query-optimizer` | 2 equality + sort | `{status:1, shipping_city:1, created_at:-1}` | 50,000 → 998 | **≈50×** |
| `query-performance-tuning` | 2 equality + range + sort | `{customer_id:1, status:1, created_at:-1}` | 50,000 → 10 | **≈5,000×** |
| `indexing` | 1 equality + range + sort | `{status:1, created_at:-1, total_amount:1}` | 50,000 → 8,899 | **≈5.6×** |

**Every skill turns a 50,000-document `COLLSCAN` into an `IXSCAN`.** The magnitude of the win
tracks **selectivity** exactly as the article predicts: high-cardinality leading equality fields
(`order_id`, `customer_id`) yield 1000×–50000× reductions; low-cardinality predicates
(`status`, coarse ranges) yield single- to double-digit reductions.

---

## 6. Honest caveats (local image vs managed Azure DocumentDB)

### 6.1 Index-backed sort and covered queries are gated OFF on `documentdb-local`

The article's *further* optimizations — **eliminating the in-memory `SORT`** (index-backed sort)
and **eliminating the `FETCH`** (covered query) — **did not reproduce** on this local image. In
every "after" plan with a sort, a blocking `SORT` stage remained, and the covered-query variant
(§4.3) kept its `FETCH`. This is a **local-image configuration limitation, not a skill error.**

**What I verified (measured):**
1. With the defaults, the flagship "after" plan is `SORT → FETCH → IXSCAN` and the covered
   variant is byte-for-byte identical to the non-covered one (`FETCH` never drops).
2. I enabled the full experimental combo at the engine level —
   `enableNewCompositeIndexOpClass=on`, `defaultUseCompositeOpClass=on`,
   `enableIndexOrderbyPushdown=on`, `forceRumIndexScantoBitmapHeapScan=off` — via
   `ALTER SYSTEM … ; SELECT pg_reload_conf();`, confirmed each shows `on` in a **fresh psql
   session**, then **dropped and recreated** the index so it would be built under the new op
   class. The Mongo-API `explain` **still** returned `SORT → FETCH → IXSCAN`.
3. Conclusion: **the gateway pins these settings per-session** (see its startup
   *"Dynamic configurations loaded"* log), so PostgreSQL-level `ALTER SYSTEM` does not change the
   Mongo-API query path. On the local image these experimental flags are simply off. (I reset all
   four GUCs back to their defaults afterward; the harness itself never touches engine config.)

**The relevant flags gated OFF on `documentdb-local`** (names/descriptions are the engine's own —
several literally say *"new experimental"*). The article demonstrates the corresponding behavior on
managed **Azure DocumentDB**, implying they are enabled there.

| Engine flag | Local default | What it governs | Relevance to the article | Evidence |
|---|---|---|---|---|
| `documentdb.enableIndexOrderbyPushdown` | `off` | pushes `ORDER BY` into the composite index | **index-backed sort** (removes the blocking `SORT`) | ✅ measured: `SORT` persists |
| `documentdb.enableNewCompositeIndexOpClass` | `off` | the "new experimental composite index opclass" | prerequisite for ordered **and** covering composite indexes | ✅ measured: combo-on + index rebuild still `SORT`/`FETCH` |
| `documentdb.defaultUseCompositeOpClass` | `off` | whether default `createIndex` builds use that op class | so the recommended index is ordered/covering | ⬤ config-observed |
| `documentdb.enableSortbyIdPushDownToPrimaryKey` | `off` | pushes `sort({_id})` onto the primary key | index-backed sort on `_id` | ⬤ config-observed |
| `documentdb.forceRumIndexScantoBitmapHeapScan` | `on` | forces a bitmap heap scan (always re-fetches heap tuples) | **prevents index-only / covered scans** → `FETCH` always present | ✅ measured: covered variant keeps `FETCH` |
| `documentdb.enableNewSelectivityMode` | `off` | the "new selectivity logic" in the planner | the article's explain surfaces `indexCosts` / `selectivity` / `correlation` | ⬤ config-observed |
| `documentdb.enableMultiIndexRumJoin` | `off` | intersecting multiple indexes for one query | combining indexes vs one compound index | ⬤ config-observed |
| `documentdb.enablePrimaryKeyCursorScan` | `off` | primary-key cursor scan for streaming cursors | faster `_id`-ordered cursor scans | ⬤ config-observed |

✅ = behavior measured in this test · ⬤ = observed in engine config (`pg_settings`), not separately behavior-tested here.

**Beyond query tuning**, the same image also ships these adjacent performance features off (not
exercised by this test, listed for completeness): `documentdb.enable_force_push_vector_index=off`
and `documentdb.enableVectorPreFilterV2=off` (vector-search push-down / pre-filter v2). HNSW,
product-quantization and half-precision vector compression **are** on.

> **How to see the full set yourself:**
> ```bash
> docker exec documentdb-local psql -h localhost -p 9712 -U documentdb -d postgres \
>   -c "SELECT name, setting, short_desc FROM pg_settings WHERE name LIKE 'documentdb.%' ORDER BY name;"
> ```

### 6.2 `executionTimeMillis` is noisy at this scale

On small result sets some "after" timings exceed "before" (e.g. §4.3, 12 ms → 28 ms) due to plan
caching, index-page warmup, and sub-millisecond measurement noise. This is itself one of the
article's lessons — *time can look fine while the query does far too much work* — so this test
reports **documents/keys examined at the scan stage** as the stable, honest signal.

### 6.3 Scale

50,000 docs vs the article's 1,000,000. The plan **shapes** and scan-work **ratios** are what
matter and are scale-independent; absolute milliseconds are not comparable.

---

## 7. Reproduce this test

```bash
# prerequisites: container up + mongosh installed + ecommerce seeded (see §2)
export DB_PASSWORD=Test1234
bash scenarios/ecommerce/query-perf-skill-test.sh          # prints the human report + a JSON block
```

The harness (`scenarios/ecommerce/query-perf-skill-test.js`) is self-contained: for each skill it
drops every non-`_id` index on `orders` (forcing the baseline), measures before, creates the
recommended index, measures after (+ the covered variant for the flagship), and drops the index —
so it is **idempotent** and leaves `orders` with only its default `_id` index.

---

## 8. Verdict

- **Dataset fit:** `ecommerce.orders` is a strong, faithful stand-in for the article's `orders`
  example — no new dataset needed.
- **Skills validated:** all four test cases (across three skills — `query-optimizer` covers two
  facets) turn a `COLLSCAN` into an `IXSCAN`, with the reduction scaling by selectivity exactly as
  the ESR guidance predicts. The recommended indexes and trigger phrases are the ones the skills
  ship.
- **Faithful limitation:** index-backed-sort and covered-query removal are environment-gated on
  the local image; they are Azure-DocumentDB-managed behaviors (per the article), not something
  the local test can demonstrate.

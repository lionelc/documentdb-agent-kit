# Quick Start: Find & Fix a Slow Query on Azure DocumentDB

**Time: ~10 minutes.** In this guide you'll run Azure DocumentDB locally, load a
sample store dataset, ask your AI coding assistant *why a query is slow*, apply the
one-line fix it recommends, and watch the same query go from scanning **50,000
documents** to just **10** — with no application code change.

You don't need to know anything about the internals. If you have Docker and an AI
coding assistant, you can follow along by copy-paste.

---

## What is this?

The **Azure DocumentDB Agent Kit** is a set of *skills* you add to your AI coding
assistant (Claude Code, Cursor, GitHub Copilot CLI, Gemini CLI, VS Code, …). Once
installed, your assistant knows how to diagnose and optimize
[Azure DocumentDB](https://learn.microsoft.com/azure/documentdb/) (the managed,
MongoDB-compatible database) — reading `explain()` output, designing indexes, and
more.

Install the skills (one time):

```bash
npx skills add Azure/documentdb-agent-kit
```

For the sample data and the ready-made test used below, also grab the repo:

```bash
git clone https://github.com/Azure/documentdb-agent-kit
cd documentdb-agent-kit
```

> **Preview:** Azure DocumentDB and this kit are in public preview; details may
> change. No production SLA.

---

## Step 1 — Run DocumentDB locally

```bash
docker run -d --name documentdb-local \
  -e USERNAME=docdbadmin -e PASSWORD=Test1234 \
  ghcr.io/microsoft/documentdb/documentdb-local:latest
```

Add a Mongo shell to the container (the preview image ships without one, and the
sample-data loader uses it):

```bash
docker exec -u root documentdb-local bash -lc '
  cd /tmp && wget -q https://downloads.mongodb.com/compass/mongosh-2.3.8-linux-x64.tgz -O m.tgz &&
  tar xzf m.tgz && cp mongosh-2.3.8-linux-x64/bin/mongosh /usr/local/bin/ &&
  cp mongosh-2.3.8-linux-x64/bin/mongosh_crypt_v1.so /usr/local/lib/ 2>/dev/null; mongosh --version'
```

## Step 2 — Load the sample data

This seeds a realistic store database (`ecommerce`) — **50,000 orders**,
customers, products, and more. It takes about a minute.

```bash
export DB_PASSWORD=Test1234
bash scenarios/ecommerce/seed.sh
```

The `orders` collection starts with **no indexes** (other than the default `_id`)
— exactly the situation that makes queries slow as data grows.

---

## Step 3 — Ask your assistant why a query is slow

Here's a perfectly reasonable query — find a customer's shipped orders since the
start of the year, newest first:

```javascript
db.orders.find({
  status: "shipped",
  customer_id: "CUST_004087",
  created_at: { $gte: ISODate("2024-01-01") }
}).sort({ created_at: -1 })
```

Paste this prompt to your AI assistant (the kit's skill will pick it up):

> **"Why is this query slow, and how do I fix it?"**
> `db.orders.find({ status: "shipped", customer_id: "CUST_004087", created_at: { $gte: ISODate("2024-01-01") } }).sort({ created_at: -1 })`

Your assistant will run `explain("executionStats")` and spot the problem: a
**collection scan** (`COLLSCAN`) — the database reads **every one** of the 50,000
documents to return just 10.

> **Prefer to look yourself?** Run the same query with `.explain("executionStats")`.
> ⚠️ **Read the scan stage, not the summary.** The top-line time can look tiny (a
> few milliseconds) even during a full scan — look at the `COLLSCAN` stage, where
> `totalDocsExamined` is **50,000**.

*(No assistant handy? The kit also ships a deterministic router that names the
right skill for a question — `bash knowledge-base/kb-route.sh "why is this query slow and how do I index it"`.)*

---

## Step 4 — Apply the recommended fix

The skill recommends a single **compound index**, ordered by the **ESR rule**
(Equality → Sort → Range), with the most selective field first:

```javascript
db.orders.createIndex({ customer_id: 1, status: 1, created_at: -1 })
```

Create it (your assistant will ask for approval first):

```bash
docker exec -u documentdb documentdb-local mongosh "localhost:10260/ecommerce" \
  -u docdbadmin -p Test1234 --authenticationMechanism SCRAM-SHA-256 --tls \
  --tlsAllowInvalidCertificates --quiet \
  --eval 'db.orders.createIndex({ customer_id: 1, status: 1, created_at: -1 })'
```

## Step 5 — See the improvement

Run `explain("executionStats")` on the same query again. The `COLLSCAN` is gone,
replaced by an **index scan** (`IXSCAN`) that examines only the rows it needs:

| | Before (no index) | After (ESR index) |
|---|---|---|
| Plan | `COLLSCAN` (full scan) | `IXSCAN` (index scan) |
| Documents/keys examined | **50,000** | **10** |
| Rows returned | 10 | 10 |

**~5,000× less work per query.** Same result, a fraction of the resources — which
means more headroom to scale without adding infrastructure.

---

## Try a few more (one command)

The kit includes a ready-made test that runs several *before/after* comparisons
for you and prints the results:

```bash
export DB_PASSWORD=Test1234
bash scenarios/ecommerce/query-perf-skill-test.sh
```

You'll see the same pattern across different query shapes — the size of the win
depends on how *selective* the filter is:

| Ask your assistant… | Recommended index | Examined: before → after |
|---|---|---|
| "Does this query use an index or a collection scan?" (`find` by `order_id`) | `{ order_id: 1 }` | 50,000 → **1** |
| "Optimize `find({status, shipping_city}).sort({created_at})`" | `{ status: 1, shipping_city: 1, created_at: -1 }` | 50,000 → **998** |
| "Tune the flagship `find({status, customer_id, created_at}).sort()`" | `{ customer_id: 1, status: 1, created_at: -1 }` | 50,000 → **10** |
| "Which compound index for `find({status, total_amount:{$gt}}).sort({created_at})`?" | `{ status: 1, created_at: -1, total_amount: 1 }` | 50,000 → **8,899** |

*(The test creates each index, measures, and drops it again, so your `orders`
collection is left exactly as it started.)*

---

## What you get on managed Azure DocumentDB

This local image demonstrates the **biggest** win — turning a full scan into an
index scan. Managed **Azure DocumentDB** goes further with two optimizations that
are enabled there but not in the local preview image:

- **Index-backed sort** — the index returns rows already in order, removing the
  in-memory sort step.
- **Covered queries** — when the index contains every field the query needs, the
  database never touches the documents at all.

So on Azure the same query gets *even* faster. Learn more:
[Query Performance Tuning Guide](https://devblogs.microsoft.com/documentdb/query-performance-tuning-guide/) ·
[How to read explain output](https://learn.microsoft.com/azure/documentdb/how-to-read-explain-output).

---

## Clean up

```bash
docker rm -f documentdb-local
```

## Where to next

- **Ask your assistant** to review the indexes on your own collections, or to
  explain a slow query from your app — the same skills apply.
- **Find slow queries in production:** on Azure, route Diagnostic Logs to a Log
  Analytics workspace and rank operations in the `VCoreMongoRequests` table by
  `DurationMs`, then bring the worst offender back to your assistant.

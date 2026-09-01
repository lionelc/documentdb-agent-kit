# MongoDB to Azure DocumentDB: e-commerce compatibility quick-start

This project runs one unchanged Node.js workload against MongoDB 7 and Azure
DocumentDB. The only application setting that changes is `MONGODB_URI`.

> Azure DocumentDB and this agent kit are in public preview. This walkthrough
> is a local compatibility demonstration, not production deployment guidance.

The reusable project-generation prompt is in [`PROMPT.md`](PROMPT.md).

## What the workload covers

The deterministic seed creates:

| Collection | Documents |
|---|---:|
| `customers` | 12 |
| `products` | 16 |
| `orders` | 48 |
| `order_items` | 96 |
| `inventory` | 32 |

The four checks include one filtered `find()` and three relational-style
aggregations:

1. Orders grouped by customer, then joined to `customers` with `$lookup`.
2. One order joined to its customer and `order_items`.
3. Products joined to `inventory`, with warehouse counts and total quantity.

The queries use portable MongoDB operators only: `$match`, `$group`, `$lookup`,
`$unwind`, `$project`, `$sort`, `$limit`, `$size`, and `$sum`.

## 1. Install

```bash
cd compat
npm ci
```

The project uses one singleton `MongoClient`. Authentication and TLS stay in
the URI, so there is no MongoDB-vs-DocumentDB branch in the source.

## 2. Run against MongoDB 7

Start a clean MongoDB container:

```bash
docker rm -f mongodb-compat 2>/dev/null || true
docker run -d --name mongodb-compat \
  -p 127.0.0.1:27018:27017 \
  mongo:7.0
```

Run the seed and exact-result verification:

```bash
export MONGODB_URI='mongodb://127.0.0.1:27018/?directConnection=true'
npm test

RESULT_FILE=results/mongodb.json npm run query >/dev/null
sha256sum results/mongodb.json
```

### MongoDB result

Measured on 2026-08-31:

```text
{"database":"ecommerce_compat","counts":{"customers":12,"products":16,"orders":48,"order_items":96,"inventory":32}}
{"status":"PASS","checks":4,"query_shapes":{"find":1,"lookup_aggregations":3}}
ELAPSED_SECONDS=0.85
c6d56dddb823ada7db9d2b47fbba97adb890dbed7dee2bff0c2d0a75f1dbad30  results/mongodb.json
```

The elapsed time is one local functional run, excluding container startup. It
is recorded for reproducibility, not as a performance comparison.

## 3. Switch to Azure DocumentDB

Start a fresh local DocumentDB container using the current documented command
arguments:

```bash
export DOCDB_PASSWORD='<choose-a-password>'

docker rm -f documentdb-compat 2>/dev/null || true
docker run -d --name documentdb-compat \
  -p 127.0.0.1:10261:10260 \
  ghcr.io/microsoft/documentdb/documentdb-local:latest \
  --username docdbadmin \
  --password "$DOCDB_PASSWORD"
```

Wait for the gateway to start, then change only the endpoint:

```bash
ENCODED_PASSWORD=$(node -p 'encodeURIComponent(process.argv[1])' "$DOCDB_PASSWORD")
export MONGODB_URI="mongodb://docdbadmin:${ENCODED_PASSWORD}@127.0.0.1:10261/?tls=true&tlsAllowInvalidCertificates=true"

npm test

RESULT_FILE=results/documentdb.json npm run query >/dev/null
sha256sum results/documentdb.json
```

No JavaScript, query, schema, seed, or index definition changes are required.
The DocumentDB URI adds credentials and local self-signed-certificate options.
For Azure-hosted DocumentDB, use the connection string supplied by Azure and
do not enable `tlsAllowInvalidCertificates`.

### DocumentDB result

Measured on 2026-08-31:

```text
{"database":"ecommerce_compat","counts":{"customers":12,"products":16,"orders":48,"order_items":96,"inventory":32}}
{"status":"PASS","checks":4,"query_shapes":{"find":1,"lookup_aggregations":3}}
ELAPSED_SECONDS=1.01
c6d56dddb823ada7db9d2b47fbba97adb890dbed7dee2bff0c2d0a75f1dbad30  results/documentdb.json
```

As above, the elapsed time is diagnostic only. This walkthrough demonstrates
query and result compatibility; it is not a MongoDB-vs-DocumentDB benchmark.

## 4. Prove result parity

```bash
cmp -s results/mongodb.json results/documentdb.json \
  && echo 'MongoDB and DocumentDB results are byte-identical'

sha256sum results/mongodb.json results/documentdb.json
```

Expected:

```text
MongoDB and DocumentDB results are byte-identical
c6d56dddb823ada7db9d2b47fbba97adb890dbed7dee2bff0c2d0a75f1dbad30  results/mongodb.json
c6d56dddb823ada7db9d2b47fbba97adb890dbed7dee2bff0c2d0a75f1dbad30  results/documentdb.json
```

## Compatibility result

| Surface | MongoDB 7 | DocumentDB | Source changes |
|---|---|---|---:|
| Deterministic seed and indexes | PASS | PASS | 0 |
| Filter + projection + sort | PASS | PASS | 0 |
| `$group` + customer `$lookup` | PASS | PASS | 0 |
| Order + customer + item `$lookup` | PASS | PASS | 0 |
| Product + inventory `$lookup` | PASS | PASS | 0 |
| Exact output parity | SHA-256 `c6d56d…ad30` | SHA-256 `c6d56d…ad30` | 0 |

The compatibility claim demonstrated here is deliberately narrow and
reproducible: this e-commerce workload produced byte-identical results after an
endpoint-only switch. It does not imply that every MongoDB feature is supported;
test advanced operators against the
[DocumentDB compatibility documentation](https://learn.microsoft.com/azure/documentdb/compatibility).

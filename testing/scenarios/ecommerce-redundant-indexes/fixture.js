// fixture.js — ecommerce-redundant-indexes
// Deterministically seeds a small e-commerce database with INTENTIONALLY
// redundant indexes so index-redundancy-finder.sh has known issues to detect.
//
// Planted redundancies (the "answer key" — mirrored in expected-findings.yaml):
//   customers.{tenant_id}                  PREFIX_REDUNDANT (prefix of {tenant_id,status})
//   customers.{email}                      EXACT_DUPLICATE  (shadowed by unique {email})
//   orders.{customer_id}                   PREFIX_REDUNDANT (prefix of {customer_id,status})
//   orders.{customer_id,status}            PREFIX_REDUNDANT (prefix of 3-field index)
//   orders.{region,created_at:1}+{...:-1}  REVERSE_VARIANT
//   sessions.{ip_address}                  WRITE_TAX (zero reads, heavy writes)
//   sessions.{user_agent}                  WRITE_TAX (zero reads, heavy writes)
//
// KEEP indexes (must NOT be flagged structurally) get query traffic so they
// also show real reads:
//   customers.{tenant_id,status}, customers.{email} unique,
//   orders.{customer_id,status,created_at:-1}, orders.{region,created_at:-1}

["customers", "orders", "sessions"].forEach(function (c) {
    try { db[c].drop(); } catch (e) {}
});

// ---- customers ----
var bulk = [];
for (var i = 1; i <= 500; i++) {
    bulk.push({
        customer_id: i,
        email: "c" + i + "@shop.example",
        tenant_id: (i % 20) + 1,
        status: ["active", "inactive", "pending"][i % 3],
        created_at: new Date(2024, 0, (i % 28) + 1)
    });
}
db.customers.insertMany(bulk);
db.customers.createIndex({ tenant_id: 1 });               // PREFIX_REDUNDANT
db.customers.createIndex({ tenant_id: 1, status: 1 });    // keep
db.customers.createIndex({ email: 1 });                   // EXACT_DUPLICATE
db.customers.createIndex({ email: 1 }, { unique: true, name: "email_unique" }); // keep

// ---- orders ----
bulk = [];
for (var i = 1; i <= 1000; i++) {
    bulk.push({
        order_id: i,
        customer_id: (i % 200) + 1,
        status: ["pending", "paid", "shipped", "delivered", "cancelled"][i % 5],
        amount: (i % 500) + 10,
        region: ["NA", "EU", "APAC"][i % 3],
        created_at: new Date(2024, (i % 12), (i % 28) + 1)
    });
}
db.orders.insertMany(bulk);
db.orders.createIndex({ customer_id: 1 });                                  // PREFIX_REDUNDANT
db.orders.createIndex({ customer_id: 1, status: 1 });                       // PREFIX_REDUNDANT
db.orders.createIndex({ customer_id: 1, status: 1, created_at: -1 });       // keep
db.orders.createIndex({ region: 1, created_at: 1 });                        // REVERSE_VARIANT
db.orders.createIndex({ region: 1, created_at: -1 });                       // keep

// ---- sessions (unused indexes + heavy writes -> WRITE_TAX) ----
bulk = [];
for (var i = 1; i <= 200; i++) {
    bulk.push({
        session_id: "sess_" + i,
        user_id: (i % 100) + 1,
        ip_address: "10.0." + (i % 256) + "." + ((i * 7) % 256),
        user_agent: "Mozilla/5.0 fixture",
        created_at: new Date()
    });
}
db.sessions.insertMany(bulk);
for (var i = 1; i <= 150; i++) {
    db.sessions.updateOne({ session_id: "sess_" + i }, { $set: { last_seen: new Date() } });
}
db.sessions.createIndex({ ip_address: 1 });   // WRITE_TAX
db.sessions.createIndex({ user_agent: 1 });   // WRITE_TAX
db.sessions.createIndex({ user_id: 1 });      // also unused -> WRITE_TAX (informational)

// ---- generate query traffic on KEEP indexes so they show real reads ----
for (var i = 1; i <= 100; i++) {
    db.customers.find({ tenant_id: (i % 20) + 1, status: "active" }).limit(1).toArray();
    db.customers.find({ email: "c" + i + "@shop.example" }).limit(1).toArray();
    db.orders.find({ customer_id: (i % 200) + 1, status: "paid", created_at: { $lt: new Date() } }).limit(1).toArray();
    db.orders.find({ region: "NA", created_at: { $gte: new Date(2024, 0, 1) } }).sort({ created_at: -1 }).limit(1).toArray();
}

print("FIXTURE_READY redundant-indexes");
db.getCollectionNames().sort().forEach(function (c) {
    print("  " + c + ": " + db[c].countDocuments() + " docs, " + db[c].getIndexes().length + " indexes");
});

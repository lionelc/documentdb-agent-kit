// fixture-redundant-indexes.js — Seed a test database with intentional
// index redundancies to validate index-redundancy-finder.sh detection rules.
//
// Creates database "idx_test" with 3 collections, each containing one or
// more redundancy patterns:
//   - users:        prefix-redundant, unique-shadowed, exact-duplicate
//   - orders:       reverse-variant, prefix-redundant (3-level chain)
//   - sessions:     unused indexes (created but never queried)
//
// Recommended: use the wrapper  ->  bash scenarios/index-redundancy/seed.sh
// (it copies this file into the container and loads it, reading DB_PASSWORD).

print("=== Building redundancy test fixture in 'idx_test' database ===");

// Wipe any previous state
["users", "orders", "sessions"].forEach(function(c) {
    try { db[c].drop(); } catch(e) {}
});

// ──────────────────────────────────────────────────────────────────────
// users: small docs, demonstrate prefix/dup/unique-shadowed
// ──────────────────────────────────────────────────────────────────────
print("\n[users] inserting 5,000 docs");
var bulk = [];
for (var i = 1; i <= 5000; i++) {
    bulk.push({
        user_id: i,
        email: "u" + i + "@example.com",
        username: "user_" + i,
        tenant_id: (i % 50) + 1,
        status: ["active","inactive","pending"][i % 3],
        created_at: new Date(2024, 0, (i % 365) + 1),
        country: ["US","CA","UK","DE","FR"][i % 5]
    });
    if (bulk.length === 1000) { db.users.insertMany(bulk); bulk = []; }
}
if (bulk.length) db.users.insertMany(bulk);

print("[users] creating intentionally redundant indexes:");
// 1. Prefix-redundant: {tenant_id} vs {tenant_id, status}
db.users.createIndex({tenant_id: 1});                          // REDUNDANT (prefix of next)
db.users.createIndex({tenant_id: 1, status: 1});               // KEEP
print("  + {tenant_id}              [should be flagged: prefix-redundant]");
print("  + {tenant_id, status}      [keep]");

// 2. Exact duplicate
db.users.createIndex({email: 1}, {name: "email_idx_a"});       // KEEP (unique below)
db.users.createIndex({email: 1}, {name: "email_idx_b"});       // REDUNDANT (exact dup)
print("  + {email} email_idx_a      [will be replaced by unique below]");
print("  + {email} email_idx_b      [should be flagged: exact duplicate]");

// 3. Unique-shadowed: non-unique {username} + unique {username}
db.users.createIndex({username: 1});                            // REDUNDANT (covered by unique)
db.users.createIndex({username: 1}, {unique: true, name: "username_unique"}); // KEEP
print("  + {username}                [should be flagged: shadowed by unique]");
print("  + {username} unique         [keep]");

// ──────────────────────────────────────────────────────────────────────
// orders: bigger collection, prefix chains and reverse variants
// ──────────────────────────────────────────────────────────────────────
print("\n[orders] inserting 10,000 docs");
bulk = [];
for (var i = 1; i <= 10000; i++) {
    bulk.push({
        order_id: i,
        customer_id: (i % 1000) + 1,
        status: ["pending","paid","shipped","delivered","cancelled"][i % 5],
        amount: Math.round((Math.random() * 500 + 10) * 100) / 100,
        currency: ["USD","EUR","GBP"][i % 3],
        created_at: new Date(2024, (i % 12), (i % 28) + 1),
        region: ["NA","EU","APAC"][i % 3]
    });
    if (bulk.length === 1000) { db.orders.insertMany(bulk); bulk = []; }
}
if (bulk.length) db.orders.insertMany(bulk);

print("[orders] creating intentionally redundant indexes:");
// 4. Prefix chain: {customer_id} ⊂ {customer_id, status} ⊂ {customer_id, status, created_at}
db.orders.createIndex({customer_id: 1});                                                  // REDUNDANT
db.orders.createIndex({customer_id: 1, status: 1});                                       // REDUNDANT
db.orders.createIndex({customer_id: 1, status: 1, created_at: -1});                       // KEEP
print("  + {customer_id}                              [prefix-redundant chain]");
print("  + {customer_id, status}                      [prefix-redundant chain]");
print("  + {customer_id, status, created_at:-1}       [keep]");

// 5. Reverse variants
db.orders.createIndex({region: 1, created_at: 1});                                        // LOW (reverse below)
db.orders.createIndex({region: 1, created_at: -1});                                       // LOW (reverse above)
print("  + {region, created_at:1}    [should be flagged: reverse-variant]");
print("  + {region, created_at:-1}   [should be flagged: reverse-variant]");

// ──────────────────────────────────────────────────────────────────────
// sessions: unused indexes
// ──────────────────────────────────────────────────────────────────────
print("\n[sessions] inserting 2,000 docs (with writes — will trigger WRITE_TAX)");
bulk = [];
for (var i = 1; i <= 2000; i++) {
    bulk.push({
        session_id: "sess_" + i,
        user_id: (i % 500) + 1,
        ip_address: "10.0." + (i % 256) + "." + ((i * 7) % 256),
        user_agent: "Mozilla/5.0 fixture-test",
        created_at: new Date()
    });
}
db.sessions.insertMany(bulk);
// Cause additional write activity to bump n_tup_upd / n_tup_ins beyond threshold
for (var i = 1; i <= 1500; i++) {
    db.sessions.updateOne({session_id: "sess_" + i}, {$set: {last_seen: new Date()}});
}

print("[sessions] creating unused indexes (NOT queried, write-tax candidates):");
db.sessions.createIndex({ip_address: 1});       // UNUSED
db.sessions.createIndex({user_agent: 1});       // UNUSED
db.sessions.createIndex({user_id: 1});          // KEEP — we'll query this to differentiate
print("  + {ip_address}      [should be flagged: unused / write-tax]");
print("  + {user_agent}      [should be flagged: unused / write-tax]");
print("  + {user_id}         [we'll query this — should NOT be flagged]");

// Generate some query activity on selective indexes so they show ops > 0
print("\n[users + orders + sessions] generating query traffic on KEEP indexes...");
for (var i = 1; i <= 200; i++) {
    db.users.find({tenant_id: (i % 50) + 1, status: "active"}).limit(1).toArray();
    db.users.find({email: "u" + i + "@example.com"}).limit(1).toArray();
    db.users.find({username: "user_" + i}).limit(1).toArray();
    db.orders.find({customer_id: i, status: "paid", created_at: {$lt: new Date()}}).limit(1).toArray();
    db.orders.find({region: "NA", created_at: {$gte: new Date(2024,0,1)}}).limit(1).toArray();
    db.sessions.find({user_id: i % 500 + 1}).limit(1).toArray();
}

print("\n=== Fixture complete ===");
print("Collections: " + db.getCollectionNames().sort().join(", "));
db.getCollectionNames().sort().forEach(function(c) {
    print("  " + c + ": " + db[c].countDocuments() + " docs, " + db[c].getIndexes().length + " indexes");
});

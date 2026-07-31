// fixture.js — ecommerce-data-integrity
// Seeds an e-commerce DB with KNOWN *structural* integrity violations so
// data-integrity-check.sh (hard-logic only) has planted issues to detect.
//
// Planted issues (the answer key — mirrored in expected-findings.yaml):
//   orders.customer_id -> customers : ORPHAN FK (references to non-existent customers)
//   signups.ref_code                : TYPE INCONSISTENCY (number in some docs,
//                                     string in others — breaks indexes/queries)
//
// NOTE: value/sign/uniqueness "problems" are intentionally NOT planted here —
// the checker no longer guesses business rules from field names.

["customers", "orders", "signups"].forEach(function (c) {
    try { db[c].drop(); } catch (e) {}
});

// ---- customers: 100 valid customers (clean parent collection) ----
var bulk = [];
for (var i = 1; i <= 100; i++) {
    bulk.push({ customer_id: i, email: "c" + i + "@shop.example", name: "Customer " + i });
}
db.customers.insertMany(bulk);

// ---- orders: most reference valid customers; ~10% are orphans ----
bulk = [];
for (var i = 1; i <= 300; i++) {
    // 1 in 10 references a non-existent customer (9000+) -> ORPHAN FK
    var cust = (i % 10 === 0) ? (9000 + i) : ((i % 100) + 1);
    bulk.push({
        order_id: i,
        customer_id: cust,
        amount: (i % 400) + 5,
        status: ["pending", "paid", "shipped"][i % 3]
    });
}
db.orders.insertMany(bulk);

// ---- signups: ref_code stored with CONFLICTING scalar types -> TYPE INCONSISTENCY ----
bulk = [];
for (var i = 1; i <= 60; i++) {
    bulk.push({
        signup_id: i,
        // half numeric, half string for the same field
        ref_code: (i % 2 === 0) ? i : ("R" + i)
    });
}
db.signups.insertMany(bulk);

print("FIXTURE_READY data-integrity");
print("  customers: " + db.customers.countDocuments());
print("  orders: " + db.orders.countDocuments());
print("  signups: " + db.signups.countDocuments());

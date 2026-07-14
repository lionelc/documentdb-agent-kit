// fixture.js — ecommerce-healthy-indexes (false-positive guard)
// Seeds a HEALTHY, well-indexed e-commerce DB with NO redundant indexes.
// index-redundancy-finder.sh must report ZERO findings. This is the most
// important regression guard: it ensures a detector change doesn't start
// flagging good indexes (false positives), which would erode user trust.
//
// Design rules to stay clean:
//   * no two indexes where one is a prefix of another
//   * no exact-duplicate or unique-shadow pairs
//   * no asc/desc reverse-variant pairs
//   * every secondary index is exercised by query traffic (so none look unused)

["customers", "orders"].forEach(function (c) {
    try { db[c].drop(); } catch (e) {}
});

// ---- customers ----
var bulk = [];
for (var i = 1; i <= 500; i++) {
    bulk.push({
        customer_id: i,
        email: "c" + i + "@shop.example",
        country: ["US", "DE", "JP"][i % 3]
    });
}
db.customers.insertMany(bulk);
db.customers.createIndex({ email: 1 }, { unique: true });   // single, used
db.customers.createIndex({ country: 1 });                   // single, used

// ---- orders: one well-chosen compound index, no prefixes/reverses ----
bulk = [];
for (var i = 1; i <= 1000; i++) {
    bulk.push({
        order_id: i,
        customer_id: (i % 500) + 1,
        status: ["pending", "paid", "shipped"][i % 3],
        created_at: new Date(2024, (i % 12), (i % 28) + 1)
    });
}
db.orders.insertMany(bulk);
db.orders.createIndex({ customer_id: 1, status: 1, created_at: -1 });  // used

// ---- exercise EVERY secondary index so none are flagged as unused ----
for (var i = 1; i <= 150; i++) {
    db.customers.find({ email: "c" + i + "@shop.example" }).limit(1).toArray();
    db.customers.find({ country: "US" }).limit(1).toArray();
    db.orders.find({ customer_id: (i % 500) + 1, status: "paid", created_at: { $lt: new Date() } })
        .sort({ created_at: -1 }).limit(1).toArray();
}

print("FIXTURE_READY ecommerce-healthy-indexes");
db.getCollectionNames().sort().forEach(function (c) {
    print("  " + c + ": " + db[c].countDocuments() + " docs, " + db[c].getIndexes().length + " indexes");
});

// contoso-queries.js — Business-demand BI query suite for the Contoso model.
//
// Every query below needs ONLY scalar fields (est_value, state, territory_id,
// sales_stage, created_at, owner_id, account_id, line_items amounts). None of
// them read the big narrative/activity_log/profile text. Yet under the
// co-located schema each document access detoasts that text — the tax this
// scenario measures.
//
// Params via env:
//   CONTOSO_DB   database to run against
//   QUERY_REPS   times to repeat each query (default 5); we report the MIN ms
//                (min = least noise from container cycling / cold cache)
//
// Emits one line per query:  QRESULT {"q":"...","ms":N,"rows":M}
// and a final:               QSUMMARY {"db":"...","total_min_ms":N,"queries":K}

var DB   = process.env.CONTOSO_DB || "contoso_x1";
var REPS = parseInt(process.env.QUERY_REPS || "5");
var d = db.getSiblingDB(DB);

function timed(name, fn) {
    var best = Infinity, rows = 0;
    for (var r = 0; r < REPS; r++) {
        var t = Date.now();
        rows = fn();
        var ms = Date.now() - t;
        if (ms < best) best = ms;
    }
    print("QRESULT " + JSON.stringify({ q: name, ms: best, rows: rows }));
    return best;
}

var total = 0;

// Q1 — Open pipeline value by territory
total += timed("pipeline_by_territory", function () {
    return d.opportunities.aggregate([
        { $match: { state: "open" } },
        { $group: { _id: "$territory_id", pipeline: { $sum: "$est_value" }, deals: { $sum: 1 } } },
        { $sort: { pipeline: -1 } }
    ]).toArray().length;
});

// Q2 — Deal count & value by sales stage
total += timed("value_by_stage", function () {
    return d.opportunities.aggregate([
        { $group: { _id: "$sales_stage", n: { $sum: 1 }, value: { $sum: "$est_value" } } }
    ]).toArray().length;
});

// Q3 — Monthly bookings trend (won)
total += timed("monthly_bookings", function () {
    return d.opportunities.aggregate([
        { $match: { state: "won" } },
        { $group: { _id: { $month: "$created_at" }, booked: { $sum: "$actual_value" } } },
        { $sort: { _id: 1 } }
    ]).toArray().length;
});

// Q4 — Top accounts by pipeline
total += timed("top_accounts", function () {
    return d.opportunities.aggregate([
        { $group: { _id: "$account_id", pipeline: { $sum: "$est_value" } } },
        { $sort: { pipeline: -1 } }, { $limit: 10 }
    ]).toArray().length;
});

// Q5 — Product mix by amount (line items)
total += timed("product_mix", function () {
    return d.opportunities.aggregate([
        { $unwind: "$line_items" },
        { $group: { _id: "$line_items.product_id", revenue: { $sum: "$line_items.amount" } } },
        { $sort: { revenue: -1 } }, { $limit: 20 }
    ]).toArray().length;
});

// Q6 — Rep leaderboard (won value by owner)
total += timed("rep_leaderboard", function () {
    return d.opportunities.aggregate([
        { $match: { state: "won" } },
        { $group: { _id: "$owner_id", won: { $sum: "$actual_value" } } },
        { $sort: { won: -1 } }, { $limit: 15 }
    ]).toArray().length;
});

// Q7 — Avg deal size by industry (join to accounts)
total += timed("avg_deal_by_industry", function () {
    return d.opportunities.aggregate([
        { $lookup: { from: "accounts", localField: "account_id", foreignField: "_id", as: "acct" } },
        { $unwind: "$acct" },
        { $group: { _id: "$acct.industry", avg_deal: { $avg: "$est_value" }, n: { $sum: 1 } } },
        { $sort: { avg_deal: -1 } }
    ]).toArray().length;
});

print("QSUMMARY " + JSON.stringify({ db: DB, total_min_ms: total, queries: 7, reps: REPS }));

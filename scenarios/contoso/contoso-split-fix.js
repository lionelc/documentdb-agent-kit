// contoso-split-fix.js — Apply the DocumentDB-specific fix that
// document-bloat-advisor.sh recommends: move the large co-located text out of
// the hot 'opportunities' collection into a side collection keyed by _id.
//
// Before: opportunities = { ...scalars..., line_items, narrative, activity_log }
//         (narrative+activity_log ~6KB -> TOAST; detoasted on every scan)
// After:  opportunities      = { ...scalars..., line_items }        (small, inline)
//         opportunities_text = { _id, narrative, activity_log }     (fetched only for detail)
//
// Resumable & idempotent: re-running completes an interrupted migration.
// Env: CONTOSO_DB

var DB = process.env.CONTOSO_DB || "contoso_x1";
var d = db.getSiblingDB(DB);

// 1) Materialize the side collection from whatever text still lives on opportunities.
//    (If opportunities_text is already complete, skip the rebuild.)
var need = d.opportunities.countDocuments({ narrative: { $exists: true } });
if (need > 0 || d.opportunities_text.countDocuments() < d.opportunities.countDocuments()) {
    d.opportunities.aggregate([
        { $match: { narrative: { $exists: true } } },
        { $project: { narrative: 1, activity_log: 1 } },
        { $merge: { into: "opportunities_text", on: "_id", whenMatched: "replace", whenNotMatched: "insert" } }
    ]);
}

// 2) Strip the big text from the hot collection (idempotent; resumes if killed).
var res = d.opportunities.updateMany(
    { $or: [ { narrative: { $exists: true } }, { activity_log: { $exists: true } } ] },
    { $unset: { narrative: "", activity_log: "" } }
);
print("unset on " + (res.modifiedCount || 0) + " opportunities");
print("opportunities=" + d.opportunities.countDocuments() +
      " opportunities_text=" + d.opportunities_text.countDocuments() +
      " remaining_with_text=" + d.opportunities.countDocuments({ narrative: { $exists: true } }));
print("DONE split-fix " + DB);

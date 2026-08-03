#!/usr/bin/env python3
"""toast-split-advisor-render.py — build the TOAST-split advisor report.

Consumes the per-collection buffer that toast-split-advisor.sh assembles (one
tab-separated line per collection, either a FIELDJSON payload or "CLEAN"), passed
via environment variables, and prints either the human report or a compact JSON
object. Kept as a standalone module (not an inline heredoc) so it can be read,
linted, and tested on its own.

Env in: REPORT_DATA, JSON_MODE (0/1), DB_NAME, FIELD_MIN, INLINE_THR,
        TOAST_RATIO, MIN_KB.
"""

import os
import json

data       = os.environ.get("REPORT_DATA", "")
json_mode  = os.environ.get("JSON_MODE", "0") == "1"
db_name    = os.environ.get("DB_NAME", "")
field_min  = int(os.environ.get("FIELD_MIN", "1024"))
inline_thr = int(os.environ.get("INLINE_THR", "2000"))
toast_ratio= float(os.environ.get("TOAST_RATIO", "0.5"))
min_kb     = os.environ.get("MIN_KB", "256")

findings = []   # flagged collections with split guidance
clean    = []   # collections with no TOAST bloat

for line in data.splitlines():
    if not line.strip():
        continue
    parts = line.split("\t", 4)
    if len(parts) < 5:
        continue
    coll, heap, toast, total, tail = parts
    heap, toast, total = int(heap), int(toast), int(total)
    ratio = (toast / (heap + toast)) if (heap + toast) > 0 else 0.0

    if tail == "CLEAN":
        clean.append({"collection": coll, "heap_bytes": heap, "toast_bytes": toast,
                      "toast_ratio": round(ratio, 4)})
        continue

    fj = json.loads(tail)
    avg = fj.get("avg_obj_size", 0) or 0
    fields = fj.get("fields", [])

    # Split candidates: the largest fields that individually exceed the threshold.
    # These are what get pushed to TOAST and should move to a side collection.
    candidates = [f for f in fields if f.get("b", 0) >= field_min]
    # If nothing crosses the threshold, still surface the single largest field so
    # the operator sees where the weight is (bloat may be spread across fields).
    largest_only = (not candidates) and fields
    show = candidates if candidates else (fields[:1] if fields else [])

    moved_bytes = sum(f["b"] for f in candidates)
    projected_hot = max(avg - moved_bytes, 0)
    stays_inline = projected_hot < inline_thr

    def pct(b):
        return round(100.0 * b / avg, 1) if avg > 0 else 0.0

    findings.append({
        "collection": coll,
        "heap_bytes": heap,
        "toast_bytes": toast,
        "total_bytes": total,
        "toast_ratio": round(ratio, 4),
        "avg_obj_size": avg,
        "sampled_docs": fj.get("sampled", 0),
        "split_candidates": [
            {"field": f["f"], "avg_bytes": f["b"], "pct_of_doc": pct(f["b"])}
            for f in show
        ],
        "candidate_threshold_bytes": field_min,
        "no_field_over_threshold": bool(largest_only),
        "projected_hot_avg_bytes": projected_hot,
        "projected_stays_inline": stays_inline,
        "recommended_side_collection": coll + "_ext",
        "side_collection_key": "_id",
        "note": "ANALYSIS ONLY — no data moved. Apply the split yourself.",
    })

if json_mode:
    print(json.dumps({
        "db": db_name,
        "flagged": len(findings),
        "findings": findings,
        "clean": clean,
        "analysis_only": True,
    }))
    raise SystemExit(0)

# ── Human report ────────────────────────────────────────────────────────────
bar = "═" * 70
print(bar)
print(" DocumentDB TOAST Split Advisor  (ANALYSIS ONLY — does not modify data)")
print(f" Database: {db_name}   flag TOAST ratio > {toast_ratio}, min {min_kb}KB, "
      f"candidate field >= {field_min}B")
print(bar)
print()

for f in findings:
    hk, tk = f["heap_bytes"] // 1024, f["toast_bytes"] // 1024
    print(f"  ⚠️  {f['collection']}")
    print(f"        heap={hk}KB  TOAST={tk}KB  (TOAST ratio {f['toast_ratio']})  "
          f"avgObjSize={f['avg_obj_size']}B  [sampled {f['sampled_docs']} docs]")
    if f["no_field_over_threshold"]:
        big = f["split_candidates"][0] if f["split_candidates"] else None
        if big:
            print(f"        no single field >= {f['candidate_threshold_bytes']}B; largest is "
                  f"'{big['field']}' ({big['avg_bytes']}B, {big['pct_of_doc']}% of doc).")
        print("        Bloat is spread across fields — review the schema rather than a"
              " single split.")
    else:
        print(f"        split candidate field(s) to MOVE into a side collection:")
        for c in f["split_candidates"]:
            print(f"          • {c['field']:<24} ~{c['avg_bytes']}B/doc  "
                  f"({c['pct_of_doc']}% of document)")
        inline = ("stays INLINE (TOAST≈0) ✅" if f["projected_stays_inline"]
                  else "still large — consider moving more fields ⚠️")
        print(f"        after moving these, hot doc ≈ {f['projected_hot_avg_bytes']}B → {inline}")
        print(f"        → create '{f['recommended_side_collection']}' keyed by "
              f"'{f['side_collection_key']}' holding those fields; keep "
              f"'{f['collection']}' scalar-only.")
    print()

for c in clean:
    print(f"  ✅  {c['collection']}  heap={c['heap_bytes']//1024}KB "
          f"TOAST={c['toast_bytes']//1024}KB (ratio {c['toast_ratio']}) — no bloat")

print()
print("─" * 70)
if not findings:
    print("  ✅ No large-document/TOAST bloat detected — nothing to split.")
else:
    print(f"  Flagged {len(findings)} collection(s). This tool ONLY reports guidance.")
    print()
    print("  Applying the split safely (DO NOT run a naive bulk update on a large")
    print("  collection — it bursts WAL, holds locks, and leaves dead-tuple bloat):")
    print("    1. Copy the candidate field(s) into the side collection, keyed by _id,")
    print("       in _id-range BATCHES (e.g. 10k docs) — copy BEFORE removing.")
    print("    2. Verify per batch that the side collection has the row, THEN $unset")
    print("       the field(s) from the hot collection for that batch.")
    print("    3. After migration, VACUUM (FULL, ANALYZE) the hot table to reclaim")
    print("       space (takes an exclusive lock + ~2x disk — schedule a window).")
    print("    4. Update the application to read the field(s) from the side")
    print("       collection on demand (extra _id lookup) — split only wins when the")
    print("       big field is read far less often than the scalars are scanned.")

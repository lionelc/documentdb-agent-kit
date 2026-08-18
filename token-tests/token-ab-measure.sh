#!/usr/bin/env bash
# token-ab-measure.sh — empirically measure the context payload (bytes -> tokens)
# of two ways to answer the same DocumentDB diagnostic question:
#
#   Path A (text skill):  load the relevant SKILL.md into context, then run the
#                         manual mongosh/psql commands that skill prescribes and
#                         feed their RAW output back into context for the LLM to
#                         interpret.
#   Path B (KB router):   run kb-route.sh (NL -> exact script; router files are
#                         executed, not loaded) and feed the SCRIPT's own compact
#                         answer into context.
#
# We measure real bytes with `wc -c` and convert with tokens ~= bytes/4.
# Output: TSV with one row per (tool, dataset). Pipe to summarize.py for a
# ratio / saving-rate table:  bash token-ab-measure.sh | python3 summarize.py
set -uo pipefail

# Repo root = parent of this script's directory (token-tests/ is a child of it),
# so the harness is portable regardless of the absolute checkout path.
KIT="${KIT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONTAINER="${CONTAINER:-documentdb-local}"
PORT="${PORT:-10260}"
PG_PORT="${PG_PORT:-9712}"
PG_USER="${PG_USER:-documentdb}"
DB_USER="${DB_USER:-docdbadmin}"
PASSWORD="${DB_PASSWORD:-}"

mongo() { # $1=db $2=eval  -> raw output bytes on stdout
    docker exec "$CONTAINER" mongosh "localhost:${PORT}/$1" \
        -u "$DB_USER" -p "$PASSWORD" --authenticationMechanism SCRAM-SHA-256 \
        --tls --tlsAllowInvalidCertificates --quiet --eval "$2" 2>/dev/null
}
bytes() { wc -c | tr -d ' '; }
tok()   { awk -v b="$1" 'BEGIN{printf "%d", (b+3)/4}'; }

[[ -z "$PASSWORD" ]] && { echo "Error: no password. Set DB_PASSWORD (e.g. export DB_PASSWORD='<your-password>')." >&2; exit 1; }

# ── Path A raw-output collectors (faithful to each skill's prescribed commands) ──
# query-optimizer skill: getIndexes + stats + $indexStats + explain + findOne(sample)
raw_query_optimizer() { # $1=db $2=coll  ; the "slow aggregation" workflow
    local db="$1" c="$2"
    mongo "$db" "JSON.stringify(db.${c}.getIndexes())"
    mongo "$db" "JSON.stringify(db.${c}.stats())"
    mongo "$db" "JSON.stringify(db.${c}.aggregate([{\$indexStats:{}}]).toArray())"
    mongo "$db" "JSON.stringify(db.${c}.aggregate([{\$group:{_id:\"\$state\",v:{\$sum:\"\$est_value\"}}}]).explain(\"executionStats\"))"
    mongo "$db" "JSON.stringify(db.${c}.findOne())"   # sample doc: pulls big text on bloated collections
}
# indexing skill: per-collection getIndexes + $indexStats across the DB
raw_indexing() { # $1=db
    local db="$1"
    local colls; colls=$(mongo "$db" "db.getCollectionNames().join(' ')")
    for c in $colls; do
        mongo "$db" "JSON.stringify(db.${c}.getIndexes())"
        mongo "$db" "JSON.stringify(db.${c}.aggregate([{\$indexStats:{}}]).toArray())"
    done
}
# data-modeling skill: NOTE — this skill is about embed-vs-reference DESIGN, not
# integrity checking; no text skill covers referential integrity, so a Path-A
# agent must improvise $lookup orphan probes. We run a representative set for the
# known datasets (what a competent agent would try by hand).
raw_data_modeling() { # $1=db
    local db="$1"
    mongo "$db" "db.getCollectionNames()"
    if [[ "$db" == ecommerce* || "$db" == test_ecom* ]]; then
        mongo "$db" "JSON.stringify(db.orders.findOne())"
        mongo "$db" "JSON.stringify(db.order_items.findOne())"
        mongo "$db" "JSON.stringify(db.orders.aggregate([{\$lookup:{from:\"customers\",localField:\"customer_id\",foreignField:\"customer_id\",as:\"m\"}},{\$match:{m:{\$size:0}}},{\$count:\"orphans\"}]).toArray())"
        mongo "$db" "JSON.stringify(db.order_items.aggregate([{\$lookup:{from:\"orders\",localField:\"order_id\",foreignField:\"order_id\",as:\"m\"}},{\$match:{m:{\$size:0}}},{\$count:\"orphans\"}]).toArray())"
        mongo "$db" "JSON.stringify(db.order_items.aggregate([{\$lookup:{from:\"products\",localField:\"product_id\",foreignField:\"product_id\",as:\"m\"}},{\$match:{m:{\$size:0}}},{\$count:\"orphans\"}]).toArray())"
        mongo "$db" "JSON.stringify(db.reviews.aggregate([{\$lookup:{from:\"products\",localField:\"product_id\",foreignField:\"product_id\",as:\"m\"}},{\$match:{m:{\$size:0}}},{\$count:\"orphans\"}]).toArray())"
    else
        mongo "$db" "JSON.stringify(db.opportunities.findOne())"
        mongo "$db" "JSON.stringify(db.opportunities.aggregate([{\$lookup:{from:\"accounts\",localField:\"account_id\",foreignField:\"_id\",as:\"m\"}},{\$match:{m:{\$size:0}}},{\$count:\"orphans\"}]).toArray())"
        mongo "$db" "JSON.stringify(db.opportunities.aggregate([{\$lookup:{from:\"campaigns\",localField:\"campaign_id\",foreignField:\"_id\",as:\"m\"}},{\$match:{m:{\$size:0}}},{\$count:\"orphans\"}]).toArray())"
    fi
}
# storage/monitoring skills give NO local commands; agent improvises psql for config/cache
raw_config_improv() { # (db-agnostic instance view an agent would eventually gather)
    docker exec "$CONTAINER" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d postgres -c \
      "SELECT name,setting,unit FROM pg_settings WHERE name IN ('shared_buffers','effective_cache_size','work_mem','maintenance_work_mem');" 2>/dev/null
    docker exec "$CONTAINER" psql -h localhost -p "$PG_PORT" -U "$PG_USER" -d postgres -c \
      "SELECT relname, heap_blks_read, heap_blks_hit FROM pg_statio_user_tables ORDER BY heap_blks_hit DESC LIMIT 20;" 2>/dev/null
}

# ── per-tool spec: tool | skill_file | pathB_script + json flag ─────────────
skill_bytes() { wc -c < "${KIT}/skills/$1/SKILL.md" | tr -d ' '; }
route_bytes() { # $1=query $2=db -> bytes of router json
    bash "${KIT}/knowledge-base/kb-route.sh" --json --db "$2" "$1" 2>/dev/null | bytes
}

printf 'tool\tdataset\tskill\tA_skill_B\tA_raw_B\tA_total_B\tA_tok\tB_route_B\tB_script_B\tB_total_B\tB_tok\tratio\n'

emit() { # tool dataset skill A_skill A_raw B_route B_script query
    local tool="$1" ds="$2" skill="$3" a_skill="$4" a_raw="$5" b_route="$6" b_script="$7"
    local a_total=$((a_skill + a_raw)) b_total=$((b_route + b_script))
    local a_tok b_tok ratio
    a_tok=$(tok "$a_total"); b_tok=$(tok "$b_total")
    ratio=$(awk -v a="$a_total" -v b="$b_total" 'BEGIN{ if(b<=0){print "-"}else{printf "%.1f", a/b} }')
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$tool" "$ds" "$skill" "$a_skill" "$a_raw" "$a_total" "$a_tok" "$b_route" "$b_script" "$b_total" "$b_tok" "$ratio"
}

# 1) document-bloat-advisor  (skill: query-optimizer)
for ds in contoso ecommerce; do
    coll="opportunities"; [[ "$ds" == "ecommerce" ]] && coll="orders"
    a_raw=$(raw_query_optimizer "$ds" "$coll" | bytes)
    b_route=$(route_bytes "why are my aggregations slow, are documents too big" "$ds")
    b_script=$(bash "${KIT}/scripts/document-bloat-advisor.sh" --db "$ds" --json 2>/dev/null | bytes)
    emit "document-bloat-advisor" "$ds" "query-optimizer" "$(skill_bytes query-optimizer)" "$a_raw" "$b_route" "$b_script"
done

# 2) index-redundancy-finder  (skill: indexing)
for ds in ecommerce idx_test; do
    a_raw=$(raw_indexing "$ds" | bytes)
    b_route=$(route_bytes "do I have redundant or unused indexes" "$ds")
    b_script=$(bash "${KIT}/scripts/index-redundancy-finder.sh" --db "$ds" --json 2>/dev/null | bytes)
    emit "index-redundancy-finder" "$ds" "indexing" "$(skill_bytes indexing)" "$a_raw" "$b_route" "$b_script"
done

# 3) perf-advisor  (skill: query-optimizer ; script has no --json -> plain output)
for ds in contoso ecommerce; do
    coll="opportunities"; [[ "$ds" == "ecommerce" ]] && coll="orders"
    a_raw=$(raw_query_optimizer "$ds" "$coll" | bytes)
    b_route=$(route_bytes "give my database a performance checkup" "$ds")
    b_script=$(bash "${KIT}/scripts/perf-advisor.sh" --db "$ds" --json 2>/dev/null | bytes)
    emit "perf-advisor" "$ds" "query-optimizer" "$(skill_bytes query-optimizer)" "$a_raw" "$b_route" "$b_script"
done

# 4) data-integrity-check  (skill: data-modeling ; script plain output)
for ds in contoso ecommerce; do
    a_raw=$(raw_data_modeling "$ds" | bytes)
    b_route=$(route_bytes "check my data integrity for orphaned references" "$ds")
    b_script=$(bash "${KIT}/scripts/data-integrity-check.sh" --db "$ds" --json 2>/dev/null | bytes)
    emit "data-integrity-check" "$ds" "data-modeling" "$(skill_bytes data-modeling)" "$a_raw" "$b_route" "$b_script"
done

# 5) db-config-advisor  (no local skill; agent improvises psql -> storage skill loaded)
for ds in contoso; do
    a_raw=$(raw_config_improv | bytes)
    b_route=$(route_bytes "is my cache big enough, should I increase shared_buffers" "$ds")
    b_script=$(bash "${KIT}/scripts/db-config-advisor.sh" --db "$ds" --json 2>/dev/null | bytes)
    emit "db-config-advisor" "$ds" "storage(no-local-cmds)" "$(skill_bytes storage)" "$a_raw" "$b_route" "$b_script"
done

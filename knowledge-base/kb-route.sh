#!/usr/bin/env bash
# kb-route.sh — DocumentDB Agent-Kit knowledge-base router.
#
# Maps a natural-language diagnostic question to the exact agent-kit script that
# answers it (ONE HOP: query -> script). Reads knowledge-base/kb.json as the
# single source of truth. Deterministic keyword/example scoring (stdlib only, no
# deps) so it works without an LLM — and gives the LLM agent a structured,
# reproducible routing decision it can trust and explain.
#
# Multi-hop troubleshooting workflows (guarded diagnostic graph) are described by
# the kb.json workflow_schema and listed with --workflows; traversal is left to
# the agent and populated over time.
#
# Usage:
#   bash knowledge-base/kb-route.sh "why are my writes slow?"        # route
#   bash knowledge-base/kb-route.sh --db mydb "audit my indexes"     # fill <db>
#   bash knowledge-base/kb-route.sh --json "check data integrity"    # machine
#   bash knowledge-base/kb-route.sh --list                           # all tools
#   bash knowledge-base/kb-route.sh --workflows                      # workflows
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB="${KB_FILE:-$HERE/kb.json}"
DB=""
JSON=0
MODE="route"
QUERY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db)        DB="$2"; shift 2;;
        --json)      JSON=1; shift;;
        --list)      MODE="list"; shift;;
        --workflows) MODE="workflows"; shift;;
        --kb)        KB="$2"; shift 2;;
        -h|--help)   sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
        *)           QUERY="${QUERY:+$QUERY }$1"; shift;;
    esac
done

command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
[[ -f "$KB" ]] || { echo "kb.json not found at: $KB" >&2; exit 1; }

# Routing engine lives in a separate, lint/test-able module (kb_route.py).
# Inputs are passed via environment variables so nothing is string-interpolated
# into code. Keeping the CLI here and the logic there avoids the fragile inline
# heredoc (a stray delimiter used to be able to silently break the router).
KB="$KB" DB="$DB" JSON="$JSON" MODE="$MODE" QUERY="$QUERY" \
    exec python3 "$HERE/kb_route.py"

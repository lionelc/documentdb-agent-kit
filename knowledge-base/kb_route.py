#!/usr/bin/env python3
"""kb_route.py — DocumentDB Agent-Kit knowledge-base router (routing engine).

Maps a natural-language diagnostic question to the exact agent-kit script that
answers it (ONE HOP: query -> script). Reads knowledge-base/kb.json as the single
source of truth. Deterministic keyword/example scoring (stdlib only, no deps) so
it works without an LLM — and gives the LLM agent a structured, reproducible
routing decision it can trust and explain.

This file is invoked by kb-route.sh (the CLI wrapper), which passes inputs via
environment variables: KB, DB, JSON, MODE, QUERY. It is a standalone module so it
can be linted, unit-tested, and imported — unlike the previous inline heredoc.

Multi-hop troubleshooting workflows (guarded diagnostic graph) are described by
the kb.json workflow_schema and listed with MODE=workflows; traversal is left to
the agent and populated over time.
"""

import json
import os
import re
import sys

STOP = set(
    "the a an is are my me i do does how why what which of to in on for and or "
    "with can should".split()
)


def tokenize(s):
    return set(re.findall(r"[a-z0-9_]+", s.lower()))


def fill(invocation, db, placeholder):
    """Substitute the <db> placeholder with the actual database name, if given."""
    if db:
        return invocation.replace(placeholder, db)
    return invocation


def score_tool(t, q_tokens, q_lower):
    """Score one tool against the query.

    Signals (additive):
      * multiword keyword phrase present as a substring -> +3.0 each
      * single-word keyword present as a query token    -> +1.5 each
      * best example-query token overlap                -> +2.5 * fraction
    Returns (score, matched_keywords).
    """
    score = 0.0
    hits = []
    for kw in t.get("keywords", []):
        kwl = kw.lower()
        if " " in kwl:
            if kwl in q_lower:
                score += 3.0
                hits.append(kw)
        else:
            if kwl in q_tokens:
                score += 1.5
                hits.append(kw)
    best_ex = 0.0
    for ex in t.get("example_queries", []):
        ex_tokens = tokenize(ex) - STOP
        ov = len(ex_tokens & q_tokens)
        frac = ov / max(1, len(ex_tokens))
        best_ex = max(best_ex, frac)
    score += 2.5 * best_ex
    return score, hits


def rank_tools(kb, query):
    """Rank all tools for a query. Returns (ranked, q_tokens, q_lower) where
    ranked is a list of (score, tool, matched_keywords) sorted best-first."""
    q_tokens = tokenize(query) - STOP
    q_lower = query.lower()

    # extra signal from routes_one_hop exact-ish matches
    route_boost = {}
    for r in kb.get("routes_one_hop", {}).get("examples", []):
        r_tokens = tokenize(r["query"]) - STOP
        ov = len(r_tokens & q_tokens)
        frac = ov / max(1, len(r_tokens))
        if frac > route_boost.get(r["tool"], 0):
            route_boost[r["tool"]] = frac

    ranked = []
    for t in kb["tools"]:
        s, hits = score_tool(t, q_tokens, q_lower)
        s += 2.0 * route_boost.get(t["id"], 0.0)
        ranked.append((s, t, hits))
    ranked.sort(key=lambda x: -x[0])
    return ranked


def run_list(kb, db, placeholder, as_json):
    if as_json:
        print(json.dumps(
            [{"id": t["id"], "title": t["title"],
              "invocation": fill(t["invocation"], db, placeholder),
              "layer": t.get("layer"), "produces": t.get("produces")}
             for t in kb["tools"]], indent=2))
        return 0
    print("Knowledge base tools (one-hop targets):")
    for t in kb["tools"]:
        print(f"\n  [{t['id']}]  {t['title']}   ({t.get('layer','')})")
        print(f"    run: {fill(t['invocation'], db, placeholder)}")
        print(f"    for: {t.get('produces','')}")
        ex = t.get("example_queries", [])
        if ex:
            print(f"    e.g. \"{ex[0]}\"")
    return 0


def run_workflows(kb, as_json):
    wfs = kb.get("workflows", [])
    if as_json:
        print(json.dumps(wfs, indent=2))
        return 0
    if not wfs:
        print("No multi-hop workflows defined yet. See kb.json workflow_schema to add one.")
        return 0
    print("Multi-hop troubleshooting workflows (guarded diagnostic graph):")
    for w in wfs:
        print(f"\n  [{w['id']}]  {w['title']}   status={w.get('status','')}")
        print(f"    entry: {w['entry']}")
        for sid, step in w.get("steps", {}).items():
            deps = step.get("depends_on", [])
            dep = f"  (after: {', '.join(deps)})" if deps else ""
            print(f"      - {sid}: tool={step['tool']}{dep}")
            for obs, edge in step.get("yields", {}).items():
                nxt = edge.get("next")
                concl = edge.get("or_conclude")
                arrow = f"-> {nxt}" if nxt else f"=> {concl}"
                print(f"          on {obs}: {arrow}")
    return 0


def run_route(kb, db, placeholder, as_json, query):
    if not query:
        print("Provide a natural-language query, or use --list / --workflows.",
              file=sys.stderr)
        return 2

    ranked = rank_tools(kb, query)
    best_s, best_t, best_hits = ranked[0]
    alternatives = [(s, t) for s, t, _ in ranked[1:] if s > 0][:2]

    if as_json:
        out = {
            "query": query,
            "match": None if best_s <= 0 else {
                "tool": best_t["id"], "title": best_t["title"], "score": round(best_s, 2),
                "matched_keywords": best_hits,
                "command": fill(best_t["invocation"], db, placeholder),
                "needs_db": (not db) and (placeholder in best_t["invocation"]),
            },
            "alternatives": [{"tool": t["id"], "score": round(s, 2)} for s, t in alternatives],
            "confident": best_s >= 2.0,
        }
        print(json.dumps(out, indent=2))
        return 0

    if best_s <= 0:
        print(f'No confident route for: "{query}"')
        print("Available tools (use --list for details):")
        for t in kb["tools"]:
            print(f"  - {t['id']}: {t.get('produces','')}")
        return 0

    conf = "high" if best_s >= 4 else ("medium" if best_s >= 2 else "low")
    print(f'Query: "{query}"')
    print(f'→ Route: [{best_t["id"]}]  {best_t["title"]}   (confidence: {conf}, score {best_s:.1f})')
    if best_hits:
        print(f'  matched: {", ".join(best_hits[:6])}')
    print(f'  run: {fill(best_t["invocation"], db, placeholder)}')
    if (not db) and (placeholder in best_t["invocation"]):
        print(f'  (supply the database: --db <name>  — replaces {placeholder})')
    if alternatives:
        print("  alternatives: " + ", ".join(f"{t['id']} ({s:.1f})" for s, t in alternatives))
    return 0


def main():
    kb_path = os.environ["KB"]
    db = os.environ.get("DB") or ""
    as_json = os.environ.get("JSON") == "1"
    mode = os.environ.get("MODE") or "route"
    query = (os.environ.get("QUERY") or "").strip()

    with open(kb_path) as fh:
        kb = json.load(fh)

    placeholder = kb.get("conventions", {}).get("db_placeholder", "<db>")

    if mode == "list":
        return run_list(kb, db, placeholder, as_json)
    if mode == "workflows":
        return run_workflows(kb, as_json)
    return run_route(kb, db, placeholder, as_json, query)


if __name__ == "__main__":
    sys.exit(main())

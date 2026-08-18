#!/usr/bin/env python3
"""kb_route_demo.py — show HOW the knowledge-base router scores and picks a tool.

Unlike kb_route.py (which just prints the winning route), this demo prints the
full scoring process for a query: every tool's score, the signal breakdown
(multiword-phrase / single-keyword / example-overlap / one-hop boost), and how
the router lands on the winner. It is a teaching / debugging aid.

Run it directly from bash (no DocumentDB container needed — routing is a pure
text layer over knowledge-base/kb.json):

    python3 knowledge-base/kb_route_demo.py
    python3 knowledge-base/kb_route_demo.py "why are my aggregations slow"
    ./knowledge-base/kb_route_demo.py                # also works (executable + shebang)

With no argument it demonstrates the document-bloat / TOAST scenario.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB_JSON = Path(os.environ.get("KB_FILE", HERE / "kb.json"))
DEFAULT_QUERY = "why are my aggregations slow even though I have indexes"


def load_engine():
    """Import the real routing engine so the demo uses the SAME logic, not a copy."""
    spec = importlib.util.spec_from_file_location("kb_route", HERE / "kb_route.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def signal_breakdown(engine, tool, q_tokens, q_lower):
    """Re-derive the per-signal contributions for one tool (mirrors score_tool)."""
    parts = []
    kw_total = 0.0
    for kw in tool.get("keywords", []):
        kwl = kw.lower()
        if " " in kwl:
            if kwl in q_lower:
                parts.append((f'keyword phrase "{kw}"', 3.0)); kw_total += 3.0
        else:
            if kwl in q_tokens:
                parts.append((f'keyword "{kw}"', 1.5)); kw_total += 1.5
    best_ex, best_ex_q = 0.0, None
    for ex in tool.get("example_queries", []):
        ex_tokens = engine.tokenize(ex) - engine.STOP
        ov = len(ex_tokens & q_tokens)
        frac = ov / max(1, len(ex_tokens))
        if frac > best_ex:
            best_ex, best_ex_q = frac, ex
    if best_ex > 0:
        parts.append((f'example overlap "{best_ex_q}" ({best_ex:.2f})', 2.5 * best_ex))
    return parts


def one_hop_boost(engine, kb, q_tokens):
    """Return {tool_id: (boost, matched_route_query)} from routes_one_hop."""
    boost = {}
    for r in kb.get("routes_one_hop", {}).get("examples", []):
        r_tokens = engine.tokenize(r["query"]) - engine.STOP
        ov = len(r_tokens & q_tokens)
        frac = ov / max(1, len(r_tokens))
        if frac > 0 and frac > boost.get(r["tool"], (0, None))[0]:
            boost[r["tool"]] = (frac, r["query"])
    return boost


def main():
    query = " ".join(sys.argv[1:]).strip() or DEFAULT_QUERY
    engine = load_engine()
    with open(KB_JSON) as fh:
        kb = json.load(fh)

    q_tokens = engine.tokenize(query) - engine.STOP
    q_lower = query.lower()
    boost = one_hop_boost(engine, kb, q_tokens)

    bar = "═" * 74
    print(bar)
    print(" KB Router — scoring walkthrough")
    print(bar)
    print(f'  Query      : "{query}"')
    print(f'  Tokens     : {sorted(q_tokens)}   (stop-words removed)')
    print(f'  KB source  : {KB_JSON}')
    print()
    print("  Scoring rules: keyword phrase +3.0 · single keyword +1.5 ·")
    print("                 best example overlap +2.5×frac · one-hop route +2.0×frac")
    print("─" * 74)

    # Rank via the REAL engine so the winner matches production exactly.
    ranked = engine.rank_tools(kb, query)

    for rank, (score, tool, hits) in enumerate(ranked, 1):
        if score <= 0:
            continue
        marker = "⭐ WINNER" if rank == 1 else f"  #{rank}"
        print(f"\n  {marker}  [{tool['id']}]  score {score:.2f}")
        for label, pts in signal_breakdown(engine, tool, q_tokens, q_lower):
            print(f"        +{pts:>4.2f}  {label}")
        if tool["id"] in boost:
            frac, rq = boost[tool["id"]]
            print(f'        +{2.0*frac:>4.2f}  one-hop route "{rq}" ({frac:.2f})')

    zero = [t["id"] for s, t, _ in ranked if s <= 0]
    if zero:
        print(f"\n  (score 0, not shown: {', '.join(zero)})")

    best_s, best_t, best_hits = ranked[0]
    conf = "high" if best_s >= 4 else ("medium" if best_s >= 2 else "low")
    runner_up = next(((s, t) for s, t, _ in ranked[1:] if s > 0), None)
    print("\n" + "─" * 74)
    print("  Decision:")
    print(f"    sort tools by score desc  →  ranked[0] wins")
    print(f"    winner     : {best_t['id']}  (score {best_s:.2f}, confidence {conf})")
    if runner_up:
        rs, rt = runner_up
        print(f"    runner-up  : {rt['id']}  (score {rs:.2f}, margin {best_s-rs:.2f})")
    print(f"    confident? : {best_s >= 2.0}  (threshold 2.0)")
    print(f"    command    : {best_t['invocation']}")
    print(bar)


if __name__ == "__main__":
    main()

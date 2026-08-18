#!/usr/bin/env python3
"""summarize.py — turn token-ab-measure.sh TSV into a ratio / saving-rate table.

Reads the harness TSV on stdin (the header row is
`tool  dataset  skill  A_skill_B  A_raw_B  A_total_B  A_tok  B_route_B  B_script_B
 B_total_B  B_tok  ratio`) and prints, per (tool, dataset):

    ratio   = A_tok / B_tok            (how many times bigger Path A is)
    saving  = (A_tok - B_tok) / A_tok  (fraction of tokens avoided by Path B)

Usage:
    bash token-ab-measure.sh | python3 summarize.py
    python3 summarize.py < results-settled.tsv
    python3 summarize.py --md < results-settled.tsv     # GitHub-markdown table
"""

import sys


def main():
    as_md = "--md" in sys.argv[1:]
    rows = []
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line or line.startswith("tool\t") or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        tool, dataset = parts[0], parts[1]
        try:
            a_tok = float(parts[6])
            b_tok = float(parts[10])
        except ValueError:
            continue
        ratio = a_tok / b_tok if b_tok else float("inf")
        saving = (a_tok - b_tok) / a_tok if a_tok else 0.0
        rows.append((tool, dataset, int(a_tok), int(b_tok), ratio, saving))

    if not rows:
        print("no data rows parsed from stdin", file=sys.stderr)
        sys.exit(1)

    if as_md:
        print("| Tool | Dataset | Path A tok | Path B tok | Ratio | Saving |")
        print("|---|---|--:|--:|--:|--:|")
        for tool, ds, a, b, ratio, saving in rows:
            print(f"| {tool} | {ds} | {a:,} | {b:,} | {ratio:.1f}× | {saving*100:.1f}% |")
    else:
        w = max(len(r[0]) for r in rows)
        print(f"{'tool':<{w}}  {'dataset':<12} {'A_tok':>7} {'B_tok':>7} "
              f"{'ratio':>7} {'saving':>7}")
        print("-" * (w + 44))
        for tool, ds, a, b, ratio, saving in rows:
            print(f"{tool:<{w}}  {ds:<12} {a:>7} {b:>7} {ratio:>6.1f}x {saving*100:>6.1f}%")

    savings = [r[5] for r in rows]
    print()
    print(f"# {len(rows)} (tool,dataset) pairs · saving range "
          f"{min(savings)*100:.0f}%–{max(savings)*100:.0f}% "
          f"· median {sorted(savings)[len(savings)//2]*100:.0f}%")


if __name__ == "__main__":
    main()

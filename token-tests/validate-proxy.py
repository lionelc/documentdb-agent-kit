#!/usr/bin/env python3
"""Validate the `bytes / 4` proxy against a real tokeniser.

WHY THIS EXISTS
---------------
`token-ab-measure.sh` estimates tokens as `bytes / 4`. The obvious objection is
that this is a rule of thumb: JSON and English prose tokenise at different
rates, so the estimate must be wrong.

It IS wrong per-file — measurably so. But the harness reports a RATIO between
two paths, and the errors largely cancel, because both paths contain a similar
mix of prose and structured output. Measured on real payloads from this repo:

    payload            bytes/4   real tokens   error
    A: SKILL.md           2449          2416     +1%
    A: raw output          613           911    -33%
    B: router json         128           161    -20%
    B: script json         423           452     -6%

    ratio  bytes/4 :  5.56x   (82.0% saving)
    ratio  real    :  5.43x   (81.6% saving)
    ratio error    :  +2.4%

So the proxy is a poor estimator of ABSOLUTE token counts and a good estimator
of the RELATIVE saving, which is what the harness actually claims.

This script re-runs that check so the claim stays verifiable rather than
becoming folklore.

    pip install tiktoken
    python3 validate-proxy.py <fileA> <fileA...> --vs <fileB> <fileB...>

Exits non-zero if the ratio error exceeds --tolerance (default 10%), which
would mean the proxy has stopped being trustworthy for this payload mix.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# o200k_base is the GPT-5-era encoding. Other model families tokenise slightly
# differently, which is itself part of the point: no single proxy is exact for
# all of them, so the harness should be judged on the ratio, not the absolute.
ENCODING = "o200k_base"


def measure(paths: list[Path], enc) -> tuple[int, int]:
    total_bytes = total_tokens = 0
    for p in paths:
        raw = p.read_bytes()
        total_bytes += len(raw)
        total_tokens += len(enc.encode(raw.decode("utf-8", errors="ignore")))
    return total_bytes, total_tokens


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path_a", nargs="+", type=Path, help="Path A payload files")
    ap.add_argument("--vs", nargs="+", type=Path, required=True,
                    help="Path B payload files")
    ap.add_argument("--tolerance", type=float, default=0.10,
                    help="max acceptable relative error on the RATIO (default 0.10)")
    args = ap.parse_args(argv)

    try:
        import tiktoken
    except ImportError:
        print("tiktoken is required:  pip install tiktoken", file=sys.stderr)
        return 2

    enc = tiktoken.get_encoding(ENCODING)

    a_bytes, a_tokens = measure(args.path_a, enc)
    b_bytes, b_tokens = measure(args.vs, enc)

    if not b_tokens or not b_bytes:
        print("Path B is empty; nothing to compare", file=sys.stderr)
        return 2

    ratio_proxy = (a_bytes / 4) / (b_bytes / 4)      # == a_bytes / b_bytes
    ratio_real = a_tokens / b_tokens
    error = ratio_proxy / ratio_real - 1

    print(f"encoding: {ENCODING}")
    print(f"{'':14} {'bytes':>8} {'bytes/4':>9} {'real tok':>9}")
    print(f"{'Path A':14} {a_bytes:>8} {a_bytes // 4:>9} {a_tokens:>9}")
    print(f"{'Path B':14} {b_bytes:>8} {b_bytes // 4:>9} {b_tokens:>9}")
    print()
    print(f"ratio  bytes/4 : {ratio_proxy:.2f}x   saving {1 - b_bytes / a_bytes:.1%}")
    print(f"ratio  real    : {ratio_real:.2f}x   saving {1 - b_tokens / a_tokens:.1%}")
    print(f"ratio error    : {error:+.1%}")

    if abs(error) > args.tolerance:
        print(f"\nFAIL: ratio error exceeds {args.tolerance:.0%}. The bytes/4 "
              f"proxy is no longer reliable for this payload mix.", file=sys.stderr)
        return 1
    print(f"\nOK: within {args.tolerance:.0%} — the proxy is sound for the ratio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

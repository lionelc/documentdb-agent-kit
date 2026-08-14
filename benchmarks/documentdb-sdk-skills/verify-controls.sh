#!/usr/bin/env bash
# verify-controls.sh — reproduce every grader-validation number in docs/REPORT.md.
#
# Runs the three control submissions against the built task image and asserts
# the expected reward for each. This is the positive/negative control pair that
# makes the benchmark trustworthy:
#
#   oracle   must score 1  — otherwise the grader cannot be satisfied and every
#                            measured score is meaningless
#   empty    must score 0  — weak, but proves missing deliverables are noticed
#   naive    must score 0  — THE important one: a fully working app with no
#                            DocumentDB best practices must still fail
#
# A grader that cannot fail is worthless; a grader that cannot pass is broken.
# This checks both directions, plus the case in between that actually matters.
#
# Usage:
#   bash build.sh              # once, to build the images
#   bash verify-controls.sh    # ~10 min: each run seeds 20k documents
#   bash verify-controls.sh --only naive

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="$HERE/tasks/orders-api-python"
IMAGE="${TASK_TAG:-documentdb-orders-api-python:latest}"
ONLY=""
[ "${1:-}" = "--only" ] && ONLY="${2:-}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Image $IMAGE not found. Run:  bash build.sh" >&2
    exit 1
fi

FAILURES=0

# run_control <name> <expected-reward> <setup-command>
run_control() {
    local name="$1" expected="$2" setup="$3"
    if [ -n "$ONLY" ] && [ "$ONLY" != "$name" ]; then return 0; fi

    echo
    echo "══════════════════════════════════════════════════════════════"
    echo "  control: $name   (expect reward=$expected)"
    echo "══════════════════════════════════════════════════════════════"

    local out
    out=$(docker run --rm \
        -v "$TASK_DIR/tests:/tests:ro" \
        -v "$TASK_DIR/solution:/solution:ro" \
        -v "$HERE/controls:/controls:ro" \
        "$IMAGE" \
        bash -c "$setup /tests/test.sh >/dev/null 2>&1; \
                 echo \"REWARD=\$(cat /logs/verifier/reward.txt)\"; \
                 python3 -c \"
import json
try:
    d = json.load(open('/output/custom_metrics.json'))
except Exception:
    raise SystemExit
print('CHECKS=%s/%s' % (d.get('checks_passed'), d.get('checks_total')))
for c in ['api','behavior','documentdb','engine','source','skills']:
    p, t = d.get('checks_%s_passed' % c), d.get('checks_%s_total' % c)
    if t: print('  %-12s %s/%s' % (c, p, t))
\"" 2>&1)

    echo "$out"

    local actual
    actual=$(echo "$out" | sed -n 's/^REWARD=//p' | tail -1)
    if [ "$actual" = "$expected" ]; then
        echo "  ✅ $name: reward=$actual as expected"
    else
        echo "  ❌ $name: reward=$actual, EXPECTED $expected" >&2
        FAILURES=$((FAILURES + 1))
    fi
}

# The oracle: copies the reference implementation into /app.
run_control oracle 1 '/solution/solve.sh >/dev/null 2>&1 &&'

# Empty: nothing in /app at all.
run_control empty 0 'true &&'

# Naive: functional, but follows no DocumentDB best practice.
run_control naive 0 'mkdir -p /app && cp -r /controls/naive-python/. /app/ && chmod +x /app/*.sh &&'

echo
echo "══════════════════════════════════════════════════════════════"
if [ "$FAILURES" -eq 0 ]; then
    echo "  ✅ all controls behaved as expected"
    exit 0
fi
echo "  ❌ $FAILURES control(s) did not behave as expected" >&2
echo "     The grader is not trustworthy until this is resolved." >&2
exit 1

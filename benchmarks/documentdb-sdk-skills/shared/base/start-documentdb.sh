#!/usr/bin/env bash
# start-documentdb — bring up DocumentDB Local inside the task container and
# wait until the Mongo-compatible gateway actually accepts authenticated
# connections.
#
# Called by the verifier runner (and available to the agent) so the database
# lifecycle is controlled by the test harness rather than by the image's
# entrypoint, which Harbor overrides.
#
# The password is generated per container and exported, never baked into the
# image — check_skills.py fails any app that hardcodes a credential, so the
# benchmark must not model bad practice itself.

set -uo pipefail

PORT="${DOCUMENTDB_PORT:-10260}"
USER_="${DOCUMENTDB_USER:-docdbadmin}"
LOG="${VERIFIER_LOG_DIR:-/logs/verifier}/documentdb.log"
mkdir -p "$(dirname "$LOG")"

if [ -z "${DOCUMENTDB_PASSWORD:-}" ]; then
    DOCUMENTDB_PASSWORD="Bench$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    export DOCUMENTDB_PASSWORD
fi

# Idempotent: a second call must not start a second gateway.
if pgrep -f "documentdb" >/dev/null 2>&1 && \
   mongosh "localhost:${PORT}/admin" -u "$USER_" -p "$DOCUMENTDB_PASSWORD" \
       --authenticationMechanism SCRAM-SHA-256 --tls --tlsAllowInvalidCertificates \
       --quiet --eval "db.runCommand({ping:1}).ok" 2>/dev/null | grep -q 1; then
    echo "[start-documentdb] already running"
    exit 0
fi

echo "[start-documentdb] starting (log: $LOG)"
ENTRY=""
for candidate in /usr/local/bin/entrypoint.sh /entrypoint.sh /usr/local/bin/start.sh; do
    [ -x "$candidate" ] && { ENTRY="$candidate"; break; }
done

if [ -z "$ENTRY" ]; then
    echo "[start-documentdb] ERROR: no entrypoint script found in the image." >&2
    echo "[start-documentdb] Looked for: /usr/local/bin/entrypoint.sh /entrypoint.sh /usr/local/bin/start.sh" >&2
    exit 1
fi

USERNAME="$USER_" PASSWORD="$DOCUMENTDB_PASSWORD" \
    nohup "$ENTRY" >"$LOG" 2>&1 &

echo "[start-documentdb] waiting for the gateway to accept connections..."
for i in $(seq 1 120); do
    if mongosh "localhost:${PORT}/admin" -u "$USER_" -p "$DOCUMENTDB_PASSWORD" \
            --authenticationMechanism SCRAM-SHA-256 --tls --tlsAllowInvalidCertificates \
            --quiet --eval "db.runCommand({ping:1}).ok" 2>/dev/null | grep -q 1; then
        echo "[start-documentdb] ready after ${i}s"
        exit 0
    fi
    sleep 1
done

echo "[start-documentdb] ERROR: gateway did not become ready in 120s." >&2
echo "[start-documentdb] NOTE: DocumentDB reports a wrong password as" >&2
echo "[start-documentdb] 'MongoServerError: Invalid key' — an AUTH failure," >&2
echo "[start-documentdb] not a malformed document." >&2
tail -40 "$LOG" >&2 || true
exit 1

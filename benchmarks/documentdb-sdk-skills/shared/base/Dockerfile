# documentdb-orders-base
# ----------------------
# Shared base image for every orders-<sdk> task. Carries:
#   - DocumentDB Local (MongoDB-compatible gateway + PostgreSQL engine)
#   - mongosh (the image does NOT ship it — see below)
#   - Python 3 + verifier dependencies (pytest, pymongo, psycopg, requests)
#   - The shared /verifier/ grader library and /verifier/contracts/
#   - /logs/verifier/ ready for the reward file
#
# Per-SDK task Dockerfiles do `FROM documentdb-orders-base` and add only the
# SDK runtime + the per-task /reference and /tests payload.
#
# WHY THIS IS EASIER THAN THE COSMOS EQUIVALENT
# ---------------------------------------------
# The Cosmos benchmark's hardest problem is its base image: a Mariner-based
# emulator that runs as PID 1, needs its ENTRYPOINT overridden, and must be
# coaxed into running as an unprivileged user. DocumentDB Local is a plain
# Ubuntu container we already run daily in the kit's test suite, and its base
# layer is PUBLIC — so anyone can reproduce this image even though the MSBench
# harness itself is Microsoft-internal.

FROM ghcr.io/microsoft/documentdb/documentdb-local:latest

USER root
WORKDIR /

# The upstream image starts the gateway as its entrypoint. Harbor needs to
# drive tests/test.sh as the verifier entrypoint and the agent needs a shell,
# so reset it and let start-documentdb control the lifecycle.
ENTRYPOINT []
CMD ["/bin/bash"]

ARG MONGOSH_VERSION=2.3.8

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv ca-certificates curl jq procps \
        tar gzip unzip zip which; \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# mongosh. NOT OPTIONAL, and not present upstream.
#
# The documentdb-local image ships `psql` but NO `mongosh` (verified against
# the pristine image). Every seeder, the verifier and the reference app's
# tooling talk to the database through it. Without this the whole benchmark
# fails with "executable file not found", which reads like a broken task
# rather than a missing dependency.
# ---------------------------------------------------------------------------
RUN set -eux; \
    curl -sSL "https://downloads.mongodb.com/compass/mongosh-${MONGOSH_VERSION}-linux-x64.tgz" \
        -o /tmp/mongosh.tgz; \
    tar xzf /tmp/mongosh.tgz -C /tmp; \
    cp "/tmp/mongosh-${MONGOSH_VERSION}-linux-x64/bin/mongosh" /usr/local/bin/mongosh; \
    cp "/tmp/mongosh-${MONGOSH_VERSION}-linux-x64/bin/mongosh_crypt_v1.so" /usr/local/lib/ || true; \
    rm -rf /tmp/mongosh.tgz "/tmp/mongosh-${MONGOSH_VERSION}-linux-x64"; \
    mongosh --version

# Verifier dependencies, pinned so the benchmark is reproducible.
# psycopg is what makes check_engine.py possible: it reads the PostgreSQL
# engine underneath the Mongo API, a second observation plane the Cosmos
# benchmark does not have.
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        pytest==8.3.3 \
        pytest-json-ctrf==0.3.5 \
        requests==2.32.3 \
        pymongo==4.10.1 \
        "psycopg[binary]==3.2.3" \
        pyyaml==6.0.2

# Isolated venv for the verifier so the agent's /app/build.sh cannot shadow a
# verifier dependency by pip-installing a different pymongo into system
# site-packages. runner.sh prefers /opt/verifier-venv/bin/python.
RUN python3 -m venv /opt/verifier-venv && \
    /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.3.3 \
        pytest-json-ctrf==0.3.5 \
        requests==2.32.3 \
        pymongo==4.10.1 \
        "psycopg[binary]==3.2.3" \
        pyyaml==6.0.2

# Shared grader library + scenario contracts. Owned by the image, not by the
# agent — /app cannot modify these.
COPY shared/verifier/  /verifier/
COPY shared/contracts/ /verifier/contracts/
COPY shared/base/start-documentdb.sh /usr/local/bin/start-documentdb
RUN chmod +x /usr/local/bin/start-documentdb /verifier/runner.sh

# Remote-backend (CES) contract files. The runtime expects these at root.
COPY shared/ces/ /tmp/ces/
RUN set -eux; \
    for f in ces_activate.sh entry.sh save.sh restore.sh parse.py \
             glob_files.py cut_metadata.py secret_files.txt \
             nonsecret_metadata_keys.txt; do \
        if [ -f "/tmp/ces/$f" ]; then cp "/tmp/ces/$f" "/$f"; fi; \
    done; \
    if [ -f /tmp/ces/activate_python.sh ]; then cp /tmp/ces/activate_python.sh /opt/activate_python.sh; fi; \
    if [ -f /tmp/ces/safe_save.sh ]; then cp /tmp/ces/safe_save.sh /opt/safe_save.sh; fi; \
    rm -rf /tmp/ces; \
    chmod +x /ces_activate.sh /entry.sh /save.sh /restore.sh \
             /opt/activate_python.sh /opt/safe_save.sh 2>/dev/null || true

RUN mkdir -p /logs/verifier /app /reference /output /drop /agent /testbed && \
    chmod -R 1777 /logs /output /drop /agent /testbed /app /reference 2>/dev/null || true

# Connection settings. The agent is expected to read these from the
# environment — check_skills.py fails any app that hardcodes them.
ENV SCENARIO="orders" \
    DOCUMENTDB_HOST="localhost" \
    DOCUMENTDB_PORT="10260" \
    DOCUMENTDB_USER="docdbadmin" \
    DOCUMENTDB_DATABASE="ordersdb" \
    DOCUMENTDB_ORDERS_COLLECTION="orders" \
    PG_PORT="9712" \
    PG_USER="documentdb" \
    PG_DB="postgres" \
    APP_PORT="9080" \
    APP_WORKDIR="/app" \
    REFERENCE_DIR="/reference" \
    VERIFIER_LOG_DIR="/logs/verifier"

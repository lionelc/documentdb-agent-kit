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

# Pinned from ghcr.io/microsoft/documentdb/documentdb-local:latest on
# 2026-09-22. Update deliberately and rerun the benchmark controls when the
# base changes; a mutable tag would silently change the published environment.
ARG DOCUMENTDB_BASE=ghcr.io/microsoft/documentdb/documentdb-local@sha256:0fcf634531c1917ad0855ff9f4354aca0a5c5d8e435f08250568deb37eeb0ad5

# Install mongosh exactly as the DocumentDB Local source image does: from
# MongoDB's official multi-architecture APT repository. Keep it in a throwaway
# stage so package-manager metadata and build dependencies do not enter the
# benchmark image.
FROM ${DOCUMENTDB_BASE} AS mongosh
USER root
ARG MONGOSH_VERSION=2.3.8
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends wget ca-certificates gnupg binutils; \
    wget -qO- https://www.mongodb.org/static/pgp/server-8.0.asc \
        > /etc/apt/trusted.gpg.d/server-8.0.asc; \
    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/debian bookworm/mongodb-org/8.0 main" \
        > /etc/apt/sources.list.d/mongodb-org-8.0.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends "mongodb-mongosh=${MONGOSH_VERSION}"; \
    strip --strip-debug /usr/bin/mongosh; \
    test "$(mongosh --version | tr -d '\r')" = "${MONGOSH_VERSION}"; \
    rm -rf /var/lib/apt/lists/*

FROM ${DOCUMENTDB_BASE}

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
        tar gzip unzip zip; \
    rm -rf /var/lib/apt/lists/*
# NOTE: `which` is deliberately absent from that list. It is not a package on
# this base (it ships inside debianutils) and asking for it fails the whole
# apt transaction with "Unable to locate package which". The binary is already
# present at /usr/bin/which.

# ---------------------------------------------------------------------------
# mongosh. NOT OPTIONAL, and not present upstream.
#
# The documentdb-local image ships `psql` but NO `mongosh` (verified against
# the pristine image). Every seeder, the verifier and the reference app's
# tooling talk to the database through it. Without this the whole benchmark
# fails with "executable file not found", which reads like a broken task
# rather than a missing dependency.
#
# The package repository publishes native amd64 and arm64 builds. Only the
# stripped executable is copied from the throwaway stage.
# ---------------------------------------------------------------------------
COPY --from=mongosh /usr/bin/mongosh /usr/local/bin/mongosh
RUN set -eux; \
    test "$(mongosh --version | tr -d '\r')" = "${MONGOSH_VERSION}"

# ---------------------------------------------------------------------------
# Verifier dependencies, installed from VENDORED WHEELS with no network.
#
# `.wheels/` is populated on the host by shared/base/vendor-wheels.sh before
# `docker build` runs (see build.sh). Two reasons this is right, not a hack:
#   * files.pythonhosted.org is not reachable from Docker's VM on this network,
#     though the host can reach it;
#   * the benchmark promises the agent NO INTERNET during grading, and a pinned
#     wheel set makes the image reproducible when a fresh PyPI resolution months
#     later might not be.
#
# --no-index makes the guarantee enforceable: if a wheel is missing the build
# FAILS rather than silently reaching out to the network.
#
# No --break-system-packages: this base is Ubuntu 22.04 with pip 22.x, which
# does not have that flag (it arrived in pip 23 for PEP 668). Jammy is not
# externally-managed, so a plain install is correct here.
# ---------------------------------------------------------------------------
COPY .wheels /opt/wheels
# psycopg is what makes check_engine.py possible: it reads the PostgreSQL
# engine underneath the Mongo API, a second observation plane the Cosmos
# benchmark does not have.
RUN python3 -m pip install --no-cache-dir --no-index --find-links=/opt/wheels \
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
    /opt/verifier-venv/bin/pip install --no-cache-dir --no-index --find-links=/opt/wheels \
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

# ---------------------------------------------------------------------------
# The agent kit's skills, for the TREATMENT arm.
#
# shared/ces/runner.sh copies these into the agent's personal skills directory
# when SKILLS_ARM=kit, and installs nothing when SKILLS_ARM=control. They are
# staged into the build context by build.sh rather than widening the context to
# the whole repository.
# ---------------------------------------------------------------------------
COPY .skills /opt/documentdb-agent-kit/skills

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

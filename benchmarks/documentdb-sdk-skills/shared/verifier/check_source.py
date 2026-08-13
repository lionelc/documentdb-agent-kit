r"""Source-code checks — the STATIC, deliberately WEAKER half of the grader.

IMPORTANT: these are regex scans over the agent's source with comments
stripped (see `_strip_comments` in conftest.py). String *literals* are NOT
stripped, so every pattern here requires code adjacency (`foo\s*=`,
`Foo\s*\(`) rather than a bare keyword a log line could satisfy by accident.

WHY SO FEW CHECKS LIVE HERE
---------------------------
The Cosmos benchmark has ~520 lines of source checks because a single-node
emulator cannot prove client configuration behaviourally, so most of its
rubric has nowhere else to go.

We are not in that position. DocumentDB lets the verifier read the
PostgreSQL engine underneath, so index usage, scan behaviour and connection
reuse are graded BEHAVIOURALLY in check_engine.py. This file is therefore
small on purpose: only properties that genuinely leave no runtime trace stay
here. Prefer adding a check to check_engine.py or check_behavior.py whenever
the behaviour is observable.

The rules asserted here come from the kit's `documentdb-driver`,
`documentdb-connection` and `documentdb-data-modeling` skills.
"""
from __future__ import annotations

import re

import pytest


def _need(sdk: str, *want: str):
    if sdk not in want:
        pytest.skip(f"does not apply to {sdk} (only: {', '.join(want)})")


class TestClientLifecycle:
    """Singleton client.

    A MongoClient owns a connection pool. Constructing one per request
    exhausts server connections under load and defeats pooling entirely —
    the single most common driver mistake, and what `documentdb-driver` and
    `documentdb-connection` both open with.

    check_engine.py checks the runtime consequence; this names the cause.
    """

    def test_client_is_not_constructed_per_request(self, sdk, source_text):
        _need(sdk, "python")
        # A client built inside a request handler is the anti-pattern. Look for
        # a MongoClient(...) construction indented under a decorated route.
        route_then_client = re.compile(
            r"@\w+\.(?:get|post|put|delete|route)\([^)]*\)\s*"
            r"(?:async\s+)?def\s+\w+\([^)]*\):"
            r"(?:[^\n]*\n(?:[ \t]+[^\n]*\n)*?)*?[ \t]+\w*\s*=\s*MongoClient\s*\(",
            re.MULTILINE,
        )
        assert not route_then_client.search(source_text), (
            "A MongoClient is constructed inside a request handler. Create one "
            "client at application start-up and reuse it: each client owns a "
            "connection pool, so per-request construction exhausts server "
            "connections and defeats pooling."
        )

    def test_a_client_is_constructed_somewhere(self, sdk, source_text):
        _need(sdk, "python")
        assert re.search(r"MongoClient\s*\(", source_text), (
            "No MongoClient construction found in the source. The service must "
            "talk to DocumentDB through the MongoDB driver."
        )


class TestConnectionConfiguration:
    """Explicit pool and timeout settings.

    Defaults are not wrong, but an unset serverSelectionTimeoutMS means a
    database blip surfaces as a 30-second hang rather than a fast error. The
    `documentdb-connection` skill is entirely about making these explicit.
    """

    def test_connection_options_are_set_explicitly(self, sdk, source_text):
        _need(sdk, "python")
        options = (
            r"maxPoolSize", r"minPoolSize", r"serverSelectionTimeoutMS",
            r"connectTimeoutMS", r"socketTimeoutMS", r"retryWrites",
        )
        found = [o for o in options if re.search(o + r"\s*=", source_text)]
        assert found, (
            "MongoClient is constructed with no explicit connection options. "
            f"Set at least one of {', '.join(options)} — relying on defaults "
            "means a database blip becomes a long hang instead of a fast error."
        )


class TestTlsHygiene:
    """TLS must not be silently disabled.

    Azure DocumentDB requires TLS. Turning off certificate validation to make
    a local container work, then shipping it, is a real and common failure —
    and exactly what the `documentdb-security` skill warns about.
    """

    def test_certificate_validation_is_not_hardcoded_off(self, sdk, source_text):
        _need(sdk, "python")
        offenders = re.findall(
            r"tlsAllowInvalidCertificates\s*=\s*True|"
            r"tlsInsecure\s*=\s*True",
            source_text,
        )
        if offenders:
            # Allowed only when driven by an environment variable, which is how
            # a local-vs-cloud difference should be expressed.
            env_driven = re.search(
                r"tlsAllowInvalidCertificates\s*=\s*[^,\n)]*(?:os\.environ|getenv|"
                r"os\.getenv|settings\.|config\.)",
                source_text,
            )
            assert env_driven, (
                "TLS certificate validation is disabled with a hardcoded True "
                f"({offenders[:3]}). Azure DocumentDB requires TLS; if a local "
                "container needs a relaxed setting, drive it from an environment "
                "variable so production cannot inherit it."
            )

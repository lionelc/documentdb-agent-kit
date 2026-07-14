"""
kit.py — shared helpers for the DocumentDB Agent-Kit regression test framework.

The framework is "contract-first" (mirroring the Cosmos DB agent-kit testing-v2):
each scenario seeds a database with KNOWN planted issues, runs an agent-kit
diagnostic script against the live DocumentDB container, and asserts the script's
findings match a fixed expected-findings.yaml contract.

Because the diagnostic scripts already talk to DocumentDB via `docker exec`
(mongosh + psql), this harness only needs the Docker CLI — no DB driver.

Connection defaults match the local DocumentDB container the kit ships with and
can be overridden via environment variables.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# --- Locations -------------------------------------------------------------
HARNESS_DIR = Path(__file__).resolve().parent
TESTING_DIR = HARNESS_DIR.parent
REPO_DIR = TESTING_DIR.parent
SCRIPTS_DIR = REPO_DIR / "scripts"

# --- Connection config (env-overridable) -----------------------------------
# No baked-in credentials: the password must come from the environment. Accept
# either DOCDB_PASSWORD (harness-specific) or DB_PASSWORD (what the scripts read).
CONTAINER = os.environ.get("DOCDB_CONTAINER", "documentdb-local")
PORT = os.environ.get("DOCDB_PORT", "10260")
PG_PORT = os.environ.get("DOCDB_PG_PORT", "9712")
DB_USER = os.environ.get("DOCDB_USER", "docdbadmin")
DB_PASSWORD = os.environ.get("DOCDB_PASSWORD") or os.environ.get("DB_PASSWORD") or ""

_MONGOSH_FLAGS = [
    "-u", DB_USER, "-p", DB_PASSWORD,
    "--authenticationMechanism", "SCRAM-SHA-256",
    "--tls", "--tlsAllowInvalidCertificates", "--quiet",
]


@dataclass
class ScriptResult:
    """Result of running an agent-kit script."""
    name: str
    args: list
    returncode: int
    stdout: str
    stderr: str
    json: object = field(default=None)

    @property
    def ok(self) -> bool:
        return self.returncode == 0


# --- Docker plumbing -------------------------------------------------------
def _run(cmd, timeout=240, input_text=None):
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, input=input_text
    )


def container_running(container=CONTAINER):
    try:
        p = _run(["docker", "ps", "--format", "{{.Names}}"], timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return container in p.stdout.split()


def docker_exec(args, timeout=240, input_text=None, container=CONTAINER):
    flag = ["-i"] if input_text is not None else []
    return _run(["docker", "exec", *flag, container, *args], timeout=timeout, input_text=input_text)


# --- mongosh / fixture seeding --------------------------------------------
def mongosh_eval(db, js, container=CONTAINER, timeout=240):
    conn = f"localhost:{PORT}/{db}"
    p = docker_exec(["mongosh", conn, *_MONGOSH_FLAGS, "--eval", js],
                    timeout=timeout, container=container)
    return (p.stdout or "") + (p.stderr or "")


def seed(db, fixture_path, container=CONTAINER, timeout=300):
    """Copy a .js fixture into the container and execute it against `db`."""
    fixture_path = Path(fixture_path)
    dest = f"/tmp/_fixture_{db}.js"
    cp = _run(["docker", "cp", str(fixture_path), f"{container}:{dest}"], timeout=60)
    if cp.returncode != 0:
        raise RuntimeError(f"docker cp failed: {cp.stderr.strip()}")
    conn = f"localhost:{PORT}/{db}"
    p = docker_exec(["mongosh", conn, *_MONGOSH_FLAGS, "--file", dest],
                    timeout=timeout, container=container)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        raise RuntimeError(f"fixture seed failed (rc={p.returncode}):\n{out}")
    return out


def drop_db(db, container=CONTAINER):
    mongosh_eval(db, "db.dropDatabase()", container=container)


# --- Running agent-kit scripts --------------------------------------------
def run_script(name, *args, want_json=False, timeout=300):
    """Run scripts/<name> with args. If want_json, parse stdout as JSON.

    Passes the harness connection config to the script via environment (the
    scripts read DB_PASSWORD / DB_USER / CONTAINER_NAME / PORT / PG_PORT), so no
    credentials are baked into either the scripts or this harness.
    """
    script = SCRIPTS_DIR / name
    if not script.exists():
        raise FileNotFoundError(f"script not found: {script}")
    cmd = ["bash", str(script), *args]
    env = {
        **os.environ,
        "DB_PASSWORD": DB_PASSWORD,
        "DB_USER": DB_USER,
        "CONTAINER_NAME": CONTAINER,
        "CONTAINER": CONTAINER,
        "PORT": PORT,
        "PG_PORT": PG_PORT,
    }
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    parsed = None
    if want_json:
        try:
            parsed = json.loads(p.stdout)
        except json.JSONDecodeError:
            parsed = None
    return ScriptResult(name=name, args=list(args), returncode=p.returncode,
                        stdout=p.stdout, stderr=p.stderr, json=parsed)

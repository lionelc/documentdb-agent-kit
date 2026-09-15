from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import portable_diagnostic as portable  # noqa: E402


def test_every_diagnostic_has_python_and_powershell_entry_points():
    for name in sorted(portable.SUPPORTED):
        assert (SCRIPTS / f"{name}.sh").is_file()
        assert (SCRIPTS / f"{name}.py").is_file()
        assert (SCRIPTS / f"{name}.ps1").is_file()


def test_container_option_overrides_environment(monkeypatch):
    monkeypatch.setenv("CONTAINER_NAME", "from-env")
    assert portable.container_name(["--container", "from-cli"]) == "from-cli"
    assert portable.container_name([]) == "from-env"


def test_docker_command_uses_argument_list_and_direct_mode(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "secret with spaces")
    command = portable.docker_exec_command(
        "docdb",
        "/tmp/kit/perf-advisor.sh",
        ["--db", "sales data", "--json"],
    )
    assert command[:6] == [
        "docker",
        "exec",
        "-i",
        "-u",
        "documentdb",
        "-e",
    ]
    assert "DOCDB_DIRECT=1" in command
    assert "DB_PASSWORD=secret with spaces" in command
    assert command[-3:] == ["--db", "sales data", "--json"]


def test_help_does_not_require_docker():
    output = io.StringIO()
    assert portable.run_named("perf-advisor", ["--help"], stdout=output) == 0
    assert "without requiring Bash on the host" in output.getvalue()


def test_missing_docker_has_actionable_error(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(portable.DiagnosticError, match="Docker CLI was not found"):
        portable.run_named("perf-advisor", ["--db", "sales", "--json"])


def test_powershell_wrappers_forward_all_arguments():
    for name in sorted(portable.SUPPORTED):
        text = (SCRIPTS / f"{name}.ps1").read_text()
        assert f'-Diagnostic "{name}"' in text
        assert "@args" in text
        assert "exit $LASTEXITCODE" in text


def test_crlf_shell_checkout_is_normalized(tmp_path):
    source = tmp_path / "diagnostic.sh"
    source.write_bytes(b"#!/usr/bin/env bash\r\nset -uo pipefail\r\necho ok\r\n")
    output_dir = tmp_path / "normalized"
    output_dir.mkdir()

    normalized = portable.normalized_shell_copy(source, output_dir)

    assert normalized.read_bytes() == (
        b"#!/usr/bin/env bash\nset -uo pipefail\necho ok\n"
    )

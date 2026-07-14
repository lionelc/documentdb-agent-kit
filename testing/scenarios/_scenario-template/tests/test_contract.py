"""Contract tests — TEMPLATE.

Calibrate against the script's real output, then assert the answer key.
"""

import pytest

import kit


@pytest.fixture(scope="session")
def result(seeded_db):
    # For JSON scripts:
    #   res = kit.run_script("<script>.sh", "--db", seeded_db, "--json", want_json=True)
    # For text scripts:
    #   res = kit.run_script("<script>.sh", "--db", seeded_db)
    res = kit.run_script("<script>.sh", "--db", seeded_db)
    assert res.returncode == 0, f"script failed (rc={res.returncode})\n{res.stderr}"
    return res


@pytest.mark.skip(reason="template — implement assertions for your scenario")
def test_example(result, expected):
    assert result.ok

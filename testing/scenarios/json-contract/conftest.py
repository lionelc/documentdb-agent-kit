"""Scenario conftest: seed a small generic DB used to shape-check every
diagnostic script's --json output."""

from pathlib import Path

from conftest_base import make_seeded_db_fixture

seeded_db = make_seeded_db_fixture(
    "test_json_contract",
    Path(__file__).resolve().parent,
)

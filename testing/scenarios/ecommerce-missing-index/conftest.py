"""Scenario conftest: seed the missing-index fixture into its own database."""

from pathlib import Path

from conftest_base import make_seeded_db_fixture

seeded_db = make_seeded_db_fixture(
    "test_ecom_missing_index",
    Path(__file__).resolve().parent,
)

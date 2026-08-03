"""Scenario conftest: seed the data-integrity fixture into its own database."""

from pathlib import Path

from conftest_base import make_seeded_db_fixture

seeded_db = make_seeded_db_fixture(
    "test_ecom_integrity",
    Path(__file__).resolve().parent,
)

"""Scenario conftest: seed the healthy, well-indexed DB into its own database."""

from pathlib import Path

from conftest_base import make_seeded_db_fixture

seeded_db = make_seeded_db_fixture(
    "test_ecom_healthy_indexes",
    Path(__file__).resolve().parent,
)

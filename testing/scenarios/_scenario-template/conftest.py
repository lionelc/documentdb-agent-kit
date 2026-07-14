"""Scenario conftest: seed this scenario's fixture into its own database.

Rename the database to something unique per scenario.
"""

from pathlib import Path

from conftest_base import make_seeded_db_fixture

seeded_db = make_seeded_db_fixture(
    "test_template",
    Path(__file__).resolve().parent,
)

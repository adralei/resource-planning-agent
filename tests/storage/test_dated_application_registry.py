
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.storage.database import (
    connect_db,
)

from resource_planning_agent.storage.dated_application_registry import (
    initialize_dated_application_registry,
    read_dated_application_record,
    insert_dated_application_record,
)


FINGERPRINT = "a" * 64


class TestDatedApplicationRegistry(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "application_registry.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_dated_application_registry()

    def insert_record(self, connection):
        return insert_dated_application_record(
            connection=connection,
            plan_id="PLAN-801",
            approval_fingerprint=FINGERPRINT,
            reservation_count=2,
        )

    def test_record_saved_successfully(self):
        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            result = self.insert_record(connection)

            connection.commit()

        stored = read_dated_application_record(
            "PLAN-801"
        )

        self.assertEqual(stored, result)
        self.assertEqual(
            stored["reservation_count"],
            2,
        )

    def test_duplicate_plan_rejected(self):
        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.insert_record(connection)
            connection.commit()

        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                self.insert_record(connection)

            connection.rollback()

        stored = read_dated_application_record(
            "PLAN-801"
        )

        self.assertIsNotNone(stored)

    def test_rollback_removes_application_record(self):
        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            self.insert_record(connection)

            connection.rollback()

        self.assertIsNone(
            read_dated_application_record("PLAN-801")
        )

    def test_active_transaction_required(self):
        with closing(connect_db()) as connection:
            with self.assertRaises(ValueError):
                self.insert_record(connection)

        self.assertIsNone(
            read_dated_application_record("PLAN-801")
        )

    def test_invalid_fingerprint_and_count_rejected(self):
        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            with self.assertRaises(ValueError):
                insert_dated_application_record(
                    connection,
                    "PLAN-801",
                    "invalid-hash",
                    2,
                )

            with self.assertRaises(ValueError):
                insert_dated_application_record(
                    connection,
                    "PLAN-801",
                    FINGERPRINT,
                    0,
                )

            connection.rollback()

        self.assertIsNone(
            read_dated_application_record("PLAN-801")
        )


if __name__ == "__main__":
    unittest.main()

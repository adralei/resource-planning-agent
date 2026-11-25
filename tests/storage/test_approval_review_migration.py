
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.storage.database import (
    connect_db,
)

from resource_planning_agent.storage.approval_review_store import (
    initialize_review_case_store,
)


class TestApprovalReviewMigration(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "migration_test.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        # Eski Adim 27 semasini simule ediyoruz.
        with closing(connect_db()) as connection:
            connection.execute("""
                CREATE TABLE approval_review_cases (
                    case_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    case_status TEXT NOT NULL
                        CHECK (
                            case_status = 'awaiting_manual_review'
                        ),
                    consistency_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    case_data TEXT NOT NULL
                )
            """)

            connection.execute("""
                INSERT INTO approval_review_cases (
                    case_id,
                    plan_id,
                    case_status,
                    consistency_status,
                    created_at,
                    case_data
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "CASE-OLD-001",
                "PLAN-501",
                "awaiting_manual_review",
                "missing_registry",
                "2026-11-25T10:00:00+00:00",
                '{"legacy": true}',
            ))

    def test_migration_preserves_existing_case(self):
        initialize_review_case_store()

        with closing(connect_db()) as connection:
            row = connection.execute("""
                SELECT *
                FROM approval_review_cases
                WHERE case_id = ?
            """, ("CASE-OLD-001",)).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["plan_id"], "PLAN-501")
        self.assertEqual(
            row["case_status"],
            "awaiting_manual_review",
        )
        self.assertEqual(
            row["case_data"],
            '{"legacy": true}',
        )

    def test_reviewed_status_is_supported(self):
        initialize_review_case_store()

        with closing(connect_db()) as connection:
            connection.execute("""
                UPDATE approval_review_cases
                SET case_status = 'reviewed'
                WHERE case_id = ?
            """, ("CASE-OLD-001",))

            row = connection.execute("""
                SELECT case_status
                FROM approval_review_cases
                WHERE case_id = ?
            """, ("CASE-OLD-001",)).fetchone()

        self.assertEqual(
            row["case_status"],
            "reviewed",
        )

    def test_migration_is_repeatable_and_unique(
        self
    ):
        initialize_review_case_store()
        initialize_review_case_store()

        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                # Eski vakayi kapatiyoruz.
                connection.execute("""
                    UPDATE approval_review_cases
                    SET case_status = 'reviewed'
                    WHERE case_id = ?
                """, ("CASE-OLD-001",))

                # Ayni plan icin yeni bir vaka acilabilir.
                connection.execute("""
                    INSERT INTO approval_review_cases (
                        case_id,
                        plan_id,
                        case_status,
                        consistency_status,
                        created_at,
                        case_data
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    "CASE-NEW-001",
                    "PLAN-501",
                    "awaiting_manual_review",
                    "missing_registry",
                    "2026-11-25T11:00:00+00:00",
                    "{}",
                ))

                connection.commit()

            except Exception:
                connection.rollback()
                raise

            # Ancak ayni plana ikinci acik vaka eklenemez.
            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                connection.execute("""
                    INSERT INTO approval_review_cases (
                        case_id,
                        plan_id,
                        case_status,
                        consistency_status,
                        created_at,
                        case_data
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    "CASE-NEW-002",
                    "PLAN-501",
                    "awaiting_manual_review",
                    "missing_registry",
                    "2026-11-25T12:00:00+00:00",
                    "{}",
                ))


if __name__ == "__main__":
    unittest.main()


"""Integration tests for safe retries against persisted dated-plan state."""

import copy
import tempfile
import unittest

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.storage.database import (
    connect_db,
    PLANNING_PERIOD,
)

from resource_planning_agent.storage.approval_registry import (
    initialize_approval_registry,
)

from resource_planning_agent.storage.dated_application_registry import (
    initialize_dated_application_registry,
    read_dated_application_record,
)

from resource_planning_agent.planning.dated_capacity import (
    set_daily_capacity,
)

from resource_planning_agent.planning.dated_reservations import (
    initialize_reservation_schema,
    get_daily_reservations,
)

from resource_planning_agent.planning.dated_plan_application import (
    apply_approved_dated_plan,
)

from resource_planning_agent.planning.dated_application_retry import (
    apply_dated_plan_safely,
)


FINGERPRINT = "a" * 64

RETRY_MODULE = (
    "resource_planning_agent.planning."
    "dated_application_retry"
)

PREFLIGHT_LOCATIONS = (
    "resource_planning_agent.planning."
    "dated_application_confirmation.preflight_dated_plan",

    "resource_planning_agent.planning."
    "dated_plan_application.preflight_dated_plan",

    "resource_planning_agent.planning."
    "dated_plan_snapshot.preflight_dated_plan",
)


def make_preflight():
    reservations = [
        {
            "reservation_id": "RES-801",
            "employee_id": "EMP-001",
            "capacity_date": "2026-11-16",
            "reserved_hours": 3,
        },
        {
            "reservation_id": "RES-802",
            "employee_id": "EMP-001",
            "capacity_date": "2026-11-17",
            "reserved_hours": 2,
        },
    ]

    return {
        "status": "preflight_passed",
        "plan_id": "PLAN-801",
        "project_id": "DEMO-PROJECT-001",
        "reservation_count": len(reservations),
        "reservations": reservations,
        "approval_fingerprint": FINGERPRINT,
        "ready_for_capacity_revalidation": True,
        "applied": False,
    }


class TestDatedSafeRetryIntegration(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "safe_retry.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_reservation_schema()
        initialize_approval_registry()
        initialize_dated_application_registry()

        set_daily_capacity(
            "EMP-001",
            "2026-11-16",
            4,
        )

        set_daily_capacity(
            "EMP-001",
            "2026-11-17",
            4,
        )

        # Test fixture: bagimsiz approval kaydi.
        # Bu gercek bir yonetici onayi degildir.
        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute("""
                INSERT INTO approval_fingerprints (
                    plan_id,
                    fingerprint,
                    recorded_at
                )
                VALUES (?, ?, ?)
            """, (
                "PLAN-801",
                FINGERPRINT,
                "2026-11-27T10:00:00+00:00",
            ))

            connection.commit()

        # Yalnizca JSON plan / Preflight sinirini
        # mock ediyoruz.
        #
        # Confirmation, Application, SQLite ve
        # rezervasyon islemleri gercek calisacak.
        self.preflight_mocks = []

        for location in PREFLIGHT_LOCATIONS:
            preflight_patch = patch(
                location,
                side_effect=lambda plan_id: (
                    copy.deepcopy(make_preflight())
                ),
            )

            mocked = preflight_patch.start()
            self.addCleanup(preflight_patch.stop)

            self.preflight_mocks.append(mocked)

    def reservations_for(self, day):
        return get_daily_reservations(
            "EMP-001",
            day,
            PLANNING_PERIOD,
        )

    def assert_one_complete_application(self):
        record = read_dated_application_record(
            "PLAN-801"
        )

        self.assertIsNotNone(record)

        self.assertEqual(
            record["approval_fingerprint"],
            FINGERPRINT,
        )

        self.assertEqual(
            record["reservation_count"],
            2,
        )

        self.assertEqual(
            len(self.reservations_for("2026-11-16")),
            1,
        )

        self.assertEqual(
            len(self.reservations_for("2026-11-17")),
            1,
        )

    def test_first_application_commits_and_confirms(self):
        result = apply_dated_plan_safely(
            "PLAN-801"
        )

        self.assertEqual(
            result["outcome"],
            "newly_applied",
        )

        self.assertTrue(result["confirmed"])

        self.assertEqual(
            result["reservation_count"],
            2,
        )

        self.assert_one_complete_application()

    def test_second_application_reuses_commit(self):
        first = apply_dated_plan_safely(
            "PLAN-801"
        )

        second = apply_dated_plan_safely(
            "PLAN-801"
        )

        self.assertEqual(
            first["outcome"],
            "newly_applied",
        )

        self.assertEqual(
            second["outcome"],
            "already_applied",
        )

        self.assertTrue(second["confirmed"])

        self.assert_one_complete_application()

    def test_commit_then_response_error_is_confirmed(self):
        def apply_then_fail(plan_id):
            apply_approved_dated_plan(plan_id)

            # SQLite COMMIT tamamlandi ancak
            # cevap istemciye ulasamadi.
            raise RuntimeError(
                "Response lost after commit."
            )

        with patch(
            f"{RETRY_MODULE}.apply_approved_dated_plan",
            side_effect=apply_then_fail,
        ):
            result = apply_dated_plan_safely(
                "PLAN-801"
            )

        self.assertEqual(
            result["outcome"],
            "confirmed_after_error",
        )

        self.assertTrue(result["confirmed"])

        self.assert_one_complete_application()

        # Sonraki denemede mevcut basari taninmali.
        repeated = apply_dated_plan_safely(
            "PLAN-801"
        )

        self.assertEqual(
            repeated["outcome"],
            "already_applied",
        )

        self.assert_one_complete_application()

    def test_concurrent_requests_do_not_duplicate(self):
        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    apply_dated_plan_safely,
                    "PLAN-801",
                )
                for _ in range(2)
            ]

            results = [
                future.result()
                for future in futures
            ]

        self.assertEqual(
            len(results),
            2,
        )

        self.assertTrue(
            all(
                result["confirmed"] is True
                for result in results
            )
        )

        outcomes = {
            result["outcome"]
            for result in results
        }

        self.assertIn(
            "newly_applied",
            outcomes,
        )

        self.assertTrue(
            outcomes.issubset({
                "newly_applied",
                "already_applied",
                "confirmed_after_error",
            })
        )

        self.assertEqual(
            sum(
                result["outcome"] == "newly_applied"
                for result in results
            ),
            1,
        )

        self.assert_one_complete_application()

    def test_invalid_approval_blocks_application(self):
        # Ilk confirmation sirasinda Preflight
        # onay dogrulamasini reddediyor.
        self.preflight_mocks[0].side_effect = ValueError(
            "Approval verification failed."
        )

        with self.assertRaisesRegex(
            ValueError,
            "Approval verification failed",
        ):
            apply_dated_plan_safely(
                "PLAN-801"
            )

        self.assertIsNone(
            read_dated_application_record(
                "PLAN-801"
            )
        )

        self.assertEqual(
            self.reservations_for("2026-11-16"),
            [],
        )

        self.assertEqual(
            self.reservations_for("2026-11-17"),
            [],
        )


if __name__ == "__main__":
    unittest.main()

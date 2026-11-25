import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.approvals.approval_review_service import (
    open_approval_review_case,
)
from resource_planning_agent.storage.approval_review_store import (
    get_open_review_case_for_plan,
)


MODULE = (
    "resource_planning_agent.approvals."
    "approval_review_service"
)


def make_review_case(
    status="missing_registry",
    case_id="CASE-501",
):
    return {
        "case_id": case_id,
        "plan_id": "PLAN-501",
        "created_at": "2026-11-25T10:00:00+00:00",
        "case_status": "awaiting_manual_review",
        "consistency_status": status,
        "recommended_action": "investigate_approval_evidence",
        "reason": "Independent approval record missing.",
        "required_evidence": ["Original approval records"],
        "review_steps": ["Investigate inconsistency"],
        "manual_review_required": True,
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": False,
        "approval_granted": False,
        "registry_modified": False,
        "reservations_created": False,
    }


class TestApprovalReviewService(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "review_service.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

    @patch(f"{MODULE}.prepare_approval_review_case")
    def test_first_request_creates_case(self, prepare):
        prepare.return_value = make_review_case()

        result = open_approval_review_case("PLAN-501")

        self.assertTrue(result["created"])
        self.assertEqual(
            result["case"]["case_id"],
            "CASE-501",
        )

        stored = get_open_review_case_for_plan("PLAN-501")
        self.assertEqual(stored, result["case"])

    @patch(f"{MODULE}.prepare_approval_review_case")
    def test_second_request_reuses_case(self, prepare):
        prepare.return_value = make_review_case()

        first = open_approval_review_case("PLAN-501")
        second = open_approval_review_case("PLAN-501")

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])

        self.assertEqual(
            first["case"]["case_id"],
            second["case"]["case_id"],
        )

    @patch(f"{MODULE}.prepare_approval_review_case")
    def test_changed_consistency_requires_review(
        self, prepare
    ):
        prepare.return_value = make_review_case()

        open_approval_review_case("PLAN-501")

        prepare.return_value = make_review_case(
            "fingerprint_mismatch"
        )

        with self.assertRaisesRegex(
            ValueError,
            "manuel incelenmeli",
        ):
            open_approval_review_case("PLAN-501")

    @patch(f"{MODULE}.prepare_approval_review_case")
    def test_concurrent_requests_create_one_case(
        self, prepare
    ):
        prepare.side_effect = [
            make_review_case(case_id="CASE-501"),
            make_review_case(case_id="CASE-502"),
        ]

        original_lookup = get_open_review_case_for_plan
        initial_lookups = 0
        lookup_lock = threading.Lock()
        both_lookups_complete = threading.Barrier(2)

        def synchronized_lookup(plan_id):
            nonlocal initial_lookups

            result = original_lookup(plan_id)

            with lookup_lock:
                initial_lookups += 1
                wait_for_other_request = initial_lookups <= 2

            if wait_for_other_request:
                both_lookups_complete.wait(timeout=5)

            return result

        lookup_patch = patch(
            f"{MODULE}.get_open_review_case_for_plan",
            side_effect=synchronized_lookup,
        )

        with lookup_patch:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        open_approval_review_case,
                        "PLAN-501",
                    )
                    for _ in range(2)
                ]

                results = [
                    future.result()
                    for future in futures
                ]

        self.assertEqual(
            sum(result["created"] for result in results),
            1,
        )

        self.assertEqual(
            results[0]["case"]["case_id"],
            results[1]["case"]["case_id"],
        )


if __name__ == "__main__":
    unittest.main()

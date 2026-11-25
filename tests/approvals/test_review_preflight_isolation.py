
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.approvals.approval_review_service import (
    open_approval_review_case,
)

from resource_planning_agent.planning.dated_plan_preflight import (
    preflight_dated_plan,
)

from resource_planning_agent.planning.plan_fingerprint import (
    calculate_plan_fingerprint,
)

from resource_planning_agent.storage.approval_registry import (
    initialize_approval_registry,
    read_approval_fingerprint,
)

from resource_planning_agent.storage.approval_review_store import (
    initialize_review_case_store,
    complete_approval_review_case,
    list_approval_review_cases_for_plan,
)

from tests.planning.test_dated_plan_guard import (
    make_approved_plan,
)


SERVICE_MODULE = (
    "resource_planning_agent.approvals."
    "approval_review_service"
)


def make_review_case(case_id):
    return {
        "case_id": case_id,
        "plan_id": "PLAN-501",
        "created_at": "2026-11-25T10:00:00+00:00",
        "case_status": "awaiting_manual_review",
        "consistency_status": "missing_registry",
        "recommended_action": (
            "investigate_approval_evidence"
        ),
        "reason": (
            "Independent approval record missing."
        ),
        "required_evidence": [
            "Original approval records",
        ],
        "review_steps": [
            "Investigate missing registry entry",
        ],
        "manual_review_required": True,
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": False,
        "approval_granted": False,
        "registry_modified": False,
        "reservations_created": False,
    }


class TestReviewPreflightIsolation(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "isolation.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_approval_registry()
        initialize_review_case_store()

        self.plan = make_approved_plan()
        self.plan["approval_fingerprint"] = (
            calculate_plan_fingerprint(self.plan)
        )

        self.assertEqual(
            self.plan["plan_id"],
            "PLAN-501",
        )

        plan_patch = patch(
            "resource_planning_agent.planning."
            "dated_plan_preflight.load_plan",
            return_value=self.plan,
        )

        plan_patch.start()
        self.addCleanup(plan_patch.stop)

    def test_missing_registry_blocks_preflight(self):
        self.assertIsNone(
            read_approval_fingerprint("PLAN-501")
        )

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    @patch(
        f"{SERVICE_MODULE}.prepare_approval_review_case"
    )
    def test_open_review_does_not_unlock_preflight(
        self, prepare
    ):
        prepare.return_value = make_review_case(
            "CASE-801"
        )

        result = open_approval_review_case(
            "PLAN-501"
        )

        self.assertTrue(result["created"])
        self.assertFalse(
            result["case"]["approval_granted"]
        )

        self.assertIsNone(
            read_approval_fingerprint("PLAN-501")
        )

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    @patch(
        f"{SERVICE_MODULE}.prepare_approval_review_case"
    )
    def test_completed_review_does_not_unlock_preflight(
        self, prepare
    ):
        prepare.return_value = make_review_case(
            "CASE-801"
        )

        original_plan = copy.deepcopy(self.plan)

        open_approval_review_case("PLAN-501")

        completed = complete_approval_review_case(
            "CASE-801",
            "manager_project",
            "Independent approval evidence is missing.",
        )

        self.assertEqual(
            completed["case_status"],
            "reviewed",
        )

        self.assertFalse(
            completed["approval_granted"]
        )
        self.assertFalse(
            completed["registry_modified"]
        )
        self.assertFalse(
            completed["reservations_created"]
        )

        self.assertEqual(
            self.plan,
            original_plan,
        )

        self.assertIsNone(
            read_approval_fingerprint("PLAN-501")
        )

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    @patch(
        f"{SERVICE_MODULE}.prepare_approval_review_case"
    )
    def test_reopened_review_still_blocks_preflight(
        self, prepare
    ):
        prepare.side_effect = [
            make_review_case("CASE-801"),
            make_review_case("CASE-802"),
        ]

        first = open_approval_review_case(
            "PLAN-501"
        )

        complete_approval_review_case(
            first["case"]["case_id"],
            "manager_project",
            "More evidence is required.",
        )

        second = open_approval_review_case(
            "PLAN-501"
        )

        self.assertTrue(second["created"])
        self.assertNotEqual(
            first["case"]["case_id"],
            second["case"]["case_id"],
        )

        history = list_approval_review_cases_for_plan(
            "PLAN-501"
        )

        self.assertEqual(len(history), 2)

        self.assertEqual(
            [
                item["case_status"]
                for item in history
            ],
            [
                "reviewed",
                "awaiting_manual_review",
            ],
        )

        self.assertIsNone(
            read_approval_fingerprint("PLAN-501")
        )

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")


if __name__ == "__main__":
    unittest.main()

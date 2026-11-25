
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.approvals.approval_review_service import (
    open_approval_review_case,
)

from resource_planning_agent.storage.approval_review_store import (
    initialize_review_case_store,
    complete_approval_review_case,
    get_open_review_case_for_plan,
    list_approval_review_cases_for_plan,
    save_approval_review_case,
)


SERVICE_MODULE = (
    "resource_planning_agent.approvals."
    "approval_review_service"
)


def make_review_case(
    case_id,
    plan_id="PLAN-501",
    created_at="2026-11-25T10:00:00+00:00",
):
    return {
        "case_id": case_id,
        "plan_id": plan_id,
        "created_at": created_at,
        "case_status": "awaiting_manual_review",
        "consistency_status": "missing_registry",
        "recommended_action": (
            "investigate_approval_evidence"
        ),
        "reason": "Independent approval record missing.",
        "required_evidence": [
            "Original approval records",
        ],
        "review_steps": [
            "Investigate inconsistency",
        ],
        "manual_review_required": True,
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": False,
        "approval_granted": False,
        "registry_modified": False,
        "reservations_created": False,
    }


class TestApprovalReviewHistory(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "review_history.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_review_case_store()

    def test_completed_case_is_preserved(self):
        first = make_review_case("CASE-801")

        save_approval_review_case(first)

        completed = complete_approval_review_case(
            "CASE-801",
            "manager_project",
            "Approval evidence investigated.",
        )

        history = list_approval_review_cases_for_plan(
            "PLAN-501"
        )

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0], completed)
        self.assertEqual(
            history[0]["case_status"],
            "reviewed",
        )
        self.assertEqual(
            history[0]["reviewed_by"],
            "manager_project",
        )

    @patch(
        f"{SERVICE_MODULE}.prepare_approval_review_case"
    )
    def test_new_case_after_completed_review(
        self, prepare
    ):
        first = make_review_case(
            "CASE-801",
            created_at="2026-11-25T10:00:00+00:00",
        )

        second = make_review_case(
            "CASE-802",
            created_at="2026-11-25T11:00:00+00:00",
        )

        prepare.side_effect = [
            copy.deepcopy(first),
            copy.deepcopy(second),
            copy.deepcopy(second),
        ]

        first_result = open_approval_review_case(
            "PLAN-501"
        )

        complete_approval_review_case(
            "CASE-801",
            "manager_project",
            "Evidence remains incomplete.",
        )

        second_result = open_approval_review_case(
            "PLAN-501"
        )

        # Tekrarlanan istekte yeni vaka acilmamali.
        repeated = open_approval_review_case(
            "PLAN-501"
        )

        history = list_approval_review_cases_for_plan(
            "PLAN-501"
        )

        self.assertTrue(first_result["created"])
        self.assertTrue(second_result["created"])
        self.assertFalse(repeated["created"])

        self.assertEqual(len(history), 2)

        self.assertEqual(
            [item["case_id"] for item in history],
            ["CASE-801", "CASE-802"],
        )

        self.assertEqual(
            [item["case_status"] for item in history],
            ["reviewed", "awaiting_manual_review"],
        )

        self.assertEqual(
            repeated["case"]["case_id"],
            "CASE-802",
        )

        open_case = get_open_review_case_for_plan(
            "PLAN-501"
        )

        self.assertEqual(
            open_case["case_id"],
            "CASE-802",
        )

    def test_history_is_isolated_by_plan(self):
        first = make_review_case(
            "CASE-801",
            plan_id="PLAN-501",
        )

        other = make_review_case(
            "CASE-901",
            plan_id="PLAN-901",
        )

        save_approval_review_case(first)
        save_approval_review_case(other)

        history = list_approval_review_cases_for_plan(
            "PLAN-501"
        )

        self.assertEqual(len(history), 1)
        self.assertEqual(
            history[0]["case_id"],
            "CASE-801",
        )

        self.assertEqual(
            list_approval_review_cases_for_plan(
                "PLAN-NOT-FOUND"
            ),
            [],
        )

    def test_review_history_does_not_grant_approval(self):
        first = make_review_case("CASE-801")

        save_approval_review_case(first)

        complete_approval_review_case(
            "CASE-801",
            "manager_project",
            "New approval workflow is still required.",
        )

        history = list_approval_review_cases_for_plan(
            "PLAN-501"
        )

        self.assertEqual(len(history), 1)

        reviewed = history[0]

        self.assertFalse(
            reviewed["approval_granted"]
        )
        self.assertFalse(
            reviewed["registry_modified"]
        )
        self.assertFalse(
            reviewed["reservations_created"]
        )
        self.assertFalse(
            reviewed["can_proceed_to_preflight"]
        )


if __name__ == "__main__":
    unittest.main()

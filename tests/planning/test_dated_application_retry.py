
import unittest
from unittest.mock import patch

from resource_planning_agent.planning.dated_application_retry import (
    apply_dated_plan_safely,
)


MODULE = (
    "resource_planning_agent.planning."
    "dated_application_retry"
)


def confirmed():
    return {
        "status": "confirmed_applied",
        "plan_id": "PLAN-801",
        "confirmed": True,
        "safe_to_retry": False,
        "reservation_count": 2,
        "approval_fingerprint": "a" * 64,
        "applied_at": "2026-11-26T10:00:00+00:00",
    }


def not_applied():
    return {
        "status": "not_applied",
        "plan_id": "PLAN-801",
        "confirmed": False,
        "safe_to_retry": True,
        "reservation_count": 0,
    }


class TestDatedApplicationRetry(unittest.TestCase):

    @patch(f"{MODULE}.apply_approved_dated_plan")
    @patch(f"{MODULE}.confirm_dated_plan_application")
    def test_already_applied_does_not_reserve_again(
        self, confirm, apply
    ):
        confirm.return_value = confirmed()

        result = apply_dated_plan_safely("PLAN-801")

        self.assertEqual(
            result["outcome"],
            "already_applied",
        )
        self.assertTrue(result["confirmed"])
        apply.assert_not_called()
        confirm.assert_called_once_with("PLAN-801")

    @patch(f"{MODULE}.apply_approved_dated_plan")
    @patch(f"{MODULE}.confirm_dated_plan_application")
    def test_new_application_is_confirmed(
        self, confirm, apply
    ):
        confirm.side_effect = [
            not_applied(),
            confirmed(),
        ]

        result = apply_dated_plan_safely("PLAN-801")

        self.assertEqual(
            result["outcome"],
            "newly_applied",
        )
        self.assertEqual(
            result["reservation_count"],
            2,
        )
        apply.assert_called_once_with("PLAN-801")
        self.assertEqual(confirm.call_count, 2)

    @patch(f"{MODULE}.apply_approved_dated_plan")
    @patch(f"{MODULE}.confirm_dated_plan_application")
    def test_commit_then_error_is_recovered(
        self, confirm, apply
    ):
        confirm.side_effect = [
            not_applied(),
            confirmed(),
        ]

        apply.side_effect = RuntimeError(
            "Response failed after commit."
        )

        result = apply_dated_plan_safely("PLAN-801")

        self.assertEqual(
            result["outcome"],
            "confirmed_after_error",
        )
        self.assertTrue(result["confirmed"])
        apply.assert_called_once_with("PLAN-801")

    @patch(f"{MODULE}.apply_approved_dated_plan")
    @patch(f"{MODULE}.confirm_dated_plan_application")
    def test_failed_application_preserves_error(
        self, confirm, apply
    ):
        confirm.side_effect = [
            not_applied(),
            not_applied(),
        ]

        apply.side_effect = ValueError(
            "Insufficient capacity."
        )

        with self.assertRaisesRegex(
            ValueError,
            "Insufficient capacity",
        ):
            apply_dated_plan_safely("PLAN-801")

        apply.assert_called_once_with("PLAN-801")

    @patch(f"{MODULE}.apply_approved_dated_plan")
    @patch(f"{MODULE}.confirm_dated_plan_application")
    def test_inconsistent_initial_confirmation_blocks(
        self, confirm, apply
    ):
        invalid = confirmed()
        invalid["confirmed"] = False

        confirm.return_value = invalid

        with self.assertRaises(ValueError):
            apply_dated_plan_safely("PLAN-801")

        apply.assert_not_called()

    @patch(f"{MODULE}.apply_approved_dated_plan")
    @patch(f"{MODULE}.confirm_dated_plan_application")
    def test_success_without_commit_confirmation_fails(
        self, confirm, apply
    ):
        confirm.side_effect = [
            not_applied(),
            not_applied(),
        ]

        with self.assertRaisesRegex(
            RuntimeError,
            "kalici",
        ):
            apply_dated_plan_safely("PLAN-801")

        apply.assert_called_once_with("PLAN-801")

    @patch(f"{MODULE}.apply_approved_dated_plan")
    @patch(f"{MODULE}.confirm_dated_plan_application")
    def test_inconsistent_retry_confirmation_rejected(
        self, confirm, apply
    ):
        confirm.side_effect = [
            not_applied(),
            ValueError("Reservation mismatch."),
        ]

        apply.side_effect = RuntimeError(
            "Application interrupted."
        )

        with self.assertRaisesRegex(
            ValueError,
            "Reservation mismatch",
        ):
            apply_dated_plan_safely("PLAN-801")

        apply.assert_called_once_with("PLAN-801")


if __name__ == "__main__":
    unittest.main()

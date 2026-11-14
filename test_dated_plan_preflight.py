
import copy
import unittest
from unittest.mock import patch

from dated_plan_preflight import preflight_dated_plan
from test_dated_plan_guard import make_approved_plan


class TestDatedPlanPreflight(unittest.TestCase):

    @patch("dated_plan_preflight.load_plan")
    def test_valid_stored_plan_passes(self, load):
        load.return_value = make_approved_plan()

        result = preflight_dated_plan("PLAN-501")

        self.assertEqual(
            result["status"], "preflight_passed"
        )
        self.assertEqual(result["reservation_count"], 2)
        self.assertFalse(result["applied"])

        load.assert_called_once_with("PLAN-501")

    @patch("dated_plan_preflight.load_plan")
    def test_unapproved_stored_plan_rejected(self, load):
        plan = make_approved_plan()
        plan["status"] = "pending_approval"
        load.return_value = plan

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    @patch("dated_plan_preflight.load_plan")
    def test_missing_dated_reservations_rejected(self, load):
        plan = make_approved_plan()
        del plan["proposal"]["dated_reservations"]
        load.return_value = plan

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    @patch("dated_plan_preflight.load_plan")
    def test_invalid_approval_scope_rejected(self, load):
        plan = copy.deepcopy(make_approved_plan())
        plan["required_approvals"][1]["scope"] = "Other"
        load.return_value = plan

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")


if __name__ == "__main__":
    unittest.main()

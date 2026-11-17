
import copy
import unittest
from unittest.mock import patch

from resource_planning_agent.planning.dated_plan_preflight import preflight_dated_plan
from tests.planning.test_dated_plan_guard import make_approved_plan

from resource_planning_agent.planning.plan_fingerprint import (
    calculate_plan_fingerprint,
)


class TestDatedPlanPreflight(unittest.TestCase):


    @patch(
        "resource_planning_agent.planning."
        "dated_plan_preflight.verify_registered_approval"
    )
    @patch(
        "resource_planning_agent.planning."
        "dated_plan_preflight.load_plan"
    )
    def test_valid_stored_plan_passes(
        self, load, verify_registry
    ):
        plan = make_approved_plan()
        plan["approval_fingerprint"] = (
            calculate_plan_fingerprint(plan)
        )

        load.return_value = plan
        verify_registry.return_value = True

        result = preflight_dated_plan("PLAN-501")

        self.assertEqual(
            result["status"], "preflight_passed"
        )
        self.assertEqual(result["reservation_count"], 2)
        self.assertFalse(result["applied"])

        verify_registry.assert_called_once_with(plan)
        load.assert_called_once_with("PLAN-501")

    @patch("resource_planning_agent.planning.dated_plan_preflight.load_plan")
    def test_unapproved_stored_plan_rejected(self, load):
        plan = make_approved_plan()
        plan["status"] = "pending_approval"
        load.return_value = plan

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    @patch("resource_planning_agent.planning.dated_plan_preflight.load_plan")
    def test_missing_dated_reservations_rejected(self, load):
        plan = make_approved_plan()
        del plan["proposal"]["dated_reservations"]
        load.return_value = plan

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    @patch("resource_planning_agent.planning.dated_plan_preflight.load_plan")
    def test_invalid_approval_scope_rejected(self, load):
        plan = copy.deepcopy(make_approved_plan())
        plan["required_approvals"][1]["scope"] = "Other"
        load.return_value = plan

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")


    @patch("resource_planning_agent.planning.dated_plan_preflight.load_plan")
    def test_missing_fingerprint_rejected(self, load):
        plan = make_approved_plan()
        load.return_value = plan

        with self.assertRaisesRegex(
            ValueError, "fingerprint"
        ):
            preflight_dated_plan("PLAN-501")

    @patch("resource_planning_agent.planning.dated_plan_preflight.load_plan")
    def test_modified_reservation_after_approval_rejected(
        self, load
    ):
        plan = make_approved_plan()

        plan["approval_fingerprint"] = (
            calculate_plan_fingerprint(plan)
        )

        # Onaydan sonra rezervasyon saati degistiriliyor.
        plan["proposal"]["dated_reservations"][0][
            "reserved_hours"
        ] = 5

        load.return_value = plan

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    @patch("resource_planning_agent.planning.dated_plan_preflight.load_plan")
    def test_invalid_fingerprint_rejected(self, load):
        plan = make_approved_plan()
        plan["approval_fingerprint"] = "invalid-hash"

        load.return_value = plan

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

    
    @patch(
        "resource_planning_agent.planning."
        "dated_plan_preflight.verify_registered_approval"
    )
    @patch(
        "resource_planning_agent.planning."
        "dated_plan_preflight.load_plan"
    )
    def test_missing_registry_approval_rejected(
        self, load, verify_registry
    ):
        plan = make_approved_plan()
        plan["approval_fingerprint"] = (
            calculate_plan_fingerprint(plan)
        )

        load.return_value = plan
        verify_registry.return_value = False

        with self.assertRaisesRegex(
            ValueError, "Bagimsiz onay kaydi"
        ):
            preflight_dated_plan("PLAN-501")

        verify_registry.assert_called_once_with(plan)

    @patch(
        "resource_planning_agent.planning."
        "dated_plan_preflight.verify_registered_approval"
    )
    @patch(
        "resource_planning_agent.planning."
        "dated_plan_preflight.load_plan"
    )
    def test_modified_registry_hash_rejected(
        self, load, verify_registry
    ):
        plan = make_approved_plan()
        plan["approval_fingerprint"] = (
            calculate_plan_fingerprint(plan)
        )

        load.return_value = plan

        # Bagimsiz kayitla eslesmeyen bir plan simule edilir.
        verify_registry.return_value = False

        with self.assertRaises(ValueError):
            preflight_dated_plan("PLAN-501")

        self.assertFalse(verify_registry.return_value)



if __name__ == "__main__":
    unittest.main()

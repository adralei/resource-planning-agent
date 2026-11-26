
import copy
import unittest
from unittest.mock import patch

from resource_planning_agent.planning.dated_plan_preflight import (
    preflight_dated_plan,
)

from resource_planning_agent.planning.plan_fingerprint import (
    calculate_plan_fingerprint,
)

from tests.planning.test_dated_plan_guard import (
    make_approved_plan,
)


MODULE = (
    "resource_planning_agent.planning."
    "dated_plan_preflight"
)


def make_valid_plan():
    plan = make_approved_plan()

    plan["approval_fingerprint"] = (
        calculate_plan_fingerprint(plan)
    )

    return plan


class TestDatedPreflightFingerprintContract(
    unittest.TestCase
):

    @patch(f"{MODULE}.verify_registered_approval")
    @patch(f"{MODULE}.load_plan")
    def test_verified_fingerprint_is_returned(
        self, load, verify_registry
    ):
        plan = make_valid_plan()

        load.return_value = plan
        verify_registry.return_value = True

        result = preflight_dated_plan(
            plan["plan_id"]
        )

        self.assertEqual(
            result["status"],
            "preflight_passed",
        )

        self.assertEqual(
            result["approval_fingerprint"],
            plan["approval_fingerprint"],
        )

        self.assertTrue(
            result["ready_for_capacity_revalidation"]
        )

        self.assertFalse(result["applied"])

        verify_registry.assert_called_once_with(plan)

    @patch(f"{MODULE}.verify_registered_approval")
    @patch(f"{MODULE}.load_plan")
    def test_modified_plan_cannot_return_fingerprint(
        self, load, verify_registry
    ):
        original = make_valid_plan()
        modified = copy.deepcopy(original)

        modified["proposal"]["dated_reservations"][0][
            "reserved_hours"
        ] += 1

        load.return_value = modified
        verify_registry.return_value = True

        with self.assertRaises(ValueError):
            preflight_dated_plan(
                original["plan_id"]
            )

        verify_registry.assert_not_called()

    @patch(f"{MODULE}.verify_registered_approval")
    @patch(f"{MODULE}.load_plan")
    def test_registry_rejection_blocks_contract(
        self, load, verify_registry
    ):
        plan = make_valid_plan()

        load.return_value = plan
        verify_registry.return_value = False

        with self.assertRaises(ValueError):
            preflight_dated_plan(
                plan["plan_id"]
            )


if __name__ == "__main__":
    unittest.main()

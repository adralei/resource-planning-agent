
"""Tests for deterministic plan fingerprints and tamper detection."""

import copy
import unittest


from resource_planning_agent.planning.plan_fingerprint import (
    calculate_plan_fingerprint,
    verify_plan_fingerprint,
)

from tests.planning.test_dated_plan_guard import (
    make_approved_plan,
)


class TestPlanFingerprint(unittest.TestCase):

    def test_same_plan_produces_same_fingerprint(self):
        plan = make_approved_plan()

        first = calculate_plan_fingerprint(plan)
        second = calculate_plan_fingerprint(
            copy.deepcopy(plan)
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertTrue(
            verify_plan_fingerprint(plan, first)
        )

    def test_modified_reservation_changes_fingerprint(self):
        original = make_approved_plan()

        approved_fingerprint = (
            calculate_plan_fingerprint(original)
        )

        modified = copy.deepcopy(original)

        modified["proposal"]["dated_reservations"][0][
            "reserved_hours"
        ] = 5

        self.assertFalse(
            verify_plan_fingerprint(
                modified,
                approved_fingerprint,
            )
        )

    def test_modified_project_changes_fingerprint(self):
        plan = make_approved_plan()

        approved_fingerprint = (
            calculate_plan_fingerprint(plan)
        )

        modified = copy.deepcopy(plan)
        modified["project_id"] = "PROJECT-OTHER"

        self.assertFalse(
            verify_plan_fingerprint(
                modified,
                approved_fingerprint,
            )
        )

    def test_missing_fields_or_invalid_hash_rejected(self):
        plan = make_approved_plan()

        del plan["proposal"]

        with self.assertRaises(ValueError):
            calculate_plan_fingerprint(plan)

        valid_plan = make_approved_plan()

        with self.assertRaises(ValueError):
            verify_plan_fingerprint(
                valid_plan,
                "invalid-hash",
            )


if __name__ == "__main__":
    unittest.main()

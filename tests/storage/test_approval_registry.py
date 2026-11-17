
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.planning.plan_fingerprint import (
    calculate_plan_fingerprint,
)
from resource_planning_agent.storage.approval_registry import (
    initialize_approval_registry,
    record_approval_fingerprint,
    read_approval_fingerprint,
    verify_registered_approval,
)
from tests.planning.test_dated_plan_guard import (
    make_approved_plan,
)


class TestApprovalRegistry(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "registry.db",
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_approval_registry()

        self.plan = make_approved_plan()
        self.plan["approval_fingerprint"] = (
            calculate_plan_fingerprint(self.plan)
        )

    def test_registration_and_verification(self):
        result = record_approval_fingerprint(self.plan)

        self.assertEqual(result["plan_id"], "PLAN-501")
        self.assertTrue(
            verify_registered_approval(self.plan)
        )

        stored = read_approval_fingerprint("PLAN-501")
        self.assertEqual(
            stored["fingerprint"],
            self.plan["approval_fingerprint"],
        )

    def test_duplicate_registration_rejected(self):
        record_approval_fingerprint(self.plan)

        with self.assertRaises(sqlite3.IntegrityError):
            record_approval_fingerprint(self.plan)

        self.assertTrue(
            verify_registered_approval(self.plan)
        )

    def test_modified_plan_rejected(self):
        record_approval_fingerprint(self.plan)

        modified = copy.deepcopy(self.plan)
        modified["proposal"]["dated_reservations"][0][
            "reserved_hours"
        ] = 5

        self.assertFalse(
            verify_registered_approval(modified)
        )

    def test_modified_plan_and_hash_rejected(self):
        record_approval_fingerprint(self.plan)

        modified = copy.deepcopy(self.plan)
        modified["proposal"]["dated_reservations"][0][
            "reserved_hours"
        ] = 5

        # Saldirgan plan JSON'undaki hash'i de degistiriyor.
        modified["approval_fingerprint"] = (
            calculate_plan_fingerprint(modified)
        )

        # SQLite'daki bagimsiz kayit hala eski hash'i tutuyor.
        self.assertFalse(
            verify_registered_approval(modified)
        )

    def test_missing_registry_record_rejected(self):
        self.assertFalse(
            verify_registered_approval(self.plan)
        )

    def test_unapproved_plan_cannot_be_registered(self):
        self.plan["status"] = "pending_approval"

        with self.assertRaises(ValueError):
            record_approval_fingerprint(self.plan)


if __name__ == "__main__":
    unittest.main()

"""SQLite kaynaklı kapasite hesaplaması için regresyon testleri."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.tools.capacity_tool import execute_capacity_tool
from resource_planning_agent.storage.database import (
    PLANNING_PERIOD,
    PRIMARY_TEAM,
    connect_db,
    initialize_database,
    read_employee_capacities,
)


class TestCapacityDatabaseIntegration(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(self.temporary_directory.name) / "capacity_integration.db",
        )
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)

    def test_primary_team_is_separate_from_external_resources(self):
        result = execute_capacity_tool({
            "required_skill": "backend",
            "required_hours": 32,
        })
        self.assertEqual(result["total_capacity"], 28)
        self.assertEqual(result["shortage"], 4)
        self.assertEqual(result["candidates"], ["Ada", "Bora"])

        everyone = read_employee_capacities(PLANNING_PERIOD)
        primary = read_employee_capacities(PLANNING_PERIOD, team=PRIMARY_TEAM)
        self.assertEqual(len(everyone), 7)
        self.assertEqual(len(primary), 3)

    def test_capacity_changes_in_sqlite_are_reflected_in_tool(self):
        initialize_database()
        with closing(connect_db()) as connection:
            connection.execute(
                """UPDATE employee_capacity
                   SET available_hours = ?
                   WHERE employee_id = ? AND planning_period = ?""",
                (4, "EMP-001", PLANNING_PERIOD),
            )

        result = execute_capacity_tool({
            "required_skill": "backend",
            "required_hours": 32,
        })
        self.assertEqual(result["total_capacity"], 16)
        self.assertEqual(result["shortage"], 16)
        # İkinci initialize_database() çağrısı değişikliği sıfırlamamalı.
        ada = next(
            e for e in read_employee_capacities(PLANNING_PERIOD, PRIMARY_TEAM)
            if e["employee_id"] == "EMP-001"
        )
        self.assertEqual(ada["available_hours"], 4)


if __name__ == "__main__":
    unittest.main()

"""Tests for dated capacity tool request validation and results."""

import json
import unittest
from unittest.mock import patch

from dated_capacity_tool import run_dated_capacity_tool


VALID_REQUEST = {
    "required_skill": "backend",
    "required_hours": 14,
    "start_date": "2026-11-16",
    "end_date": "2026-11-17",
}


class TestDatedCapacityTool(unittest.TestCase):

    @patch("dated_capacity_tool.initialize_daily_capacity_schema")
    @patch("dated_capacity_tool.check_dated_capacity")
    def test_valid_request(self, calculation, initialize):
        calculation.return_value = {
            "status": "calculated",
            "total_capacity": 12,
            "shortage": 2,
        }

        result = run_dated_capacity_tool(
            json.dumps(VALID_REQUEST)
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["shortage"], 2)
        initialize.assert_called_once()
        calculation.assert_called_once()

    @patch("dated_capacity_tool.initialize_daily_capacity_schema")
    def test_invalid_date_range(self, initialize):
        for start, end in [
            ("2026-11-18", "2026-11-16"),
            ("2026-02-30", "2026-03-01"),
            ("2026-11-01", "2026-12-02"),
        ]:
            with self.subTest(start=start, end=end):
                request = {
                    **VALID_REQUEST,
                    "start_date": start,
                    "end_date": end,
                }

                result = run_dated_capacity_tool(
                    json.dumps(request)
                )
                self.assertFalse(result["ok"])
                self.assertEqual(
                    result["error"]["code"],
                    "invalid_arguments",
                )

        initialize.assert_not_called()

    @patch("dated_capacity_tool.initialize_daily_capacity_schema")
    def test_extra_field_rejected(self, initialize):
        request = {
            **VALID_REQUEST,
            "approved": True,
        }

        result = run_dated_capacity_tool(
            json.dumps(request)
        )

        self.assertFalse(result["ok"])
        initialize.assert_not_called()

    def test_invalid_json(self):
        result = run_dated_capacity_tool("{invalid")

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["error"]["code"],
            "invalid_json",
        )

    @patch("dated_capacity_tool.initialize_daily_capacity_schema")
    @patch("dated_capacity_tool.check_dated_capacity")
    def test_missing_data_preserved(self, calculation, initialize):
        calculation.return_value = {
            "status": "missing_daily_data",
            "total_capacity": None,
            "shortage": None,
            "data_complete": False,
        }

        result = run_dated_capacity_tool(
            json.dumps(VALID_REQUEST)
        )

        self.assertTrue(result["ok"])
        self.assertIsNone(result["data"]["total_capacity"])
        self.assertFalse(result["data"]["data_complete"])


if __name__ == "__main__":
    unittest.main()

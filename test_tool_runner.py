import unittest
from unittest.mock import patch

from tool_runner import run_capacity_tool


class TestToolRunner(unittest.TestCase):
    def test_shortage_is_a_successful_tool_result(self):
        output = run_capacity_tool(
            '{"required_skill": "backend", "required_hours": 32}'
        )

        self.assertTrue(output["ok"])
        self.assertEqual(output["data"]["shortage"], 4)
        self.assertFalse(output["data"]["is_sufficient"])

    def test_broken_json_returns_error(self):
        with patch("tool_runner.execute_capacity_tool") as tool_mock:
            output = run_capacity_tool('{"required_skill":')

            self.assertFalse(output["ok"])
            self.assertEqual(output["error"]["code"], "invalid_json")
            tool_mock.assert_not_called()

    def test_negative_hours_returns_error_without_calculation(self):
        with patch("capacity_tool.check_capacity") as calculation_mock:
            output = run_capacity_tool(
                '{"required_skill": "backend", "required_hours": -5}'
            )

            self.assertFalse(output["ok"])
            self.assertEqual(
                output["error"]["code"],
                "invalid_arguments",
            )
            self.assertEqual(
                output["error"]["details"][0]["type"],
                "greater_than",
            )
            calculation_mock.assert_not_called()
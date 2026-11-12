"""Integration tests for dated-capacity tool dispatch in the agent loop."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent_loop import run_agent_turn


class TestDatedAgentIntegration(unittest.TestCase):

    @patch("agent_loop.run_dated_capacity_tool")
    def test_dated_tool_dispatch(self, dated_runner):
        dated_runner.return_value = {
            "ok": True,
            "data": {
                "required_skill": "backend",
                "required_hours": 14,
                "start_date": "2026-11-16",
                "end_date": "2026-11-17",
                "data_complete": True,
                "total_capacity": 12,
                "shortage": 2,
                "is_sufficient": False,
            },
        }

        call = SimpleNamespace(
            type="function_call",
            name="check_dated_capacity",
            arguments=json.dumps({
                "required_skill": "backend",
                "required_hours": 14,
                "start_date": "2026-11-16",
                "end_date": "2026-11-17",
            }),
            call_id="dated_call_1",
        )

        client = Mock()
        client.responses.create.side_effect = [
            SimpleNamespace(
                status="completed",
                output=[call],
                output_text="",
                usage=None,
            ),
            SimpleNamespace(
                status="completed",
                output=[],
                output_text="",
                usage=None,
            ),
        ]

        messages = [{
            "role": "user",
            "content": "16-17 Kasim icin 14 saat backend",
        }]

        answer, responses = run_agent_turn(
            client=client,
            model_name="test-model",
            instructions="Test",
            tools=[],
            messages=messages,
            run_policy_tool=Mock(),
        )

        dated_runner.assert_called_once()
        self.assertEqual(len(responses), 2)
        self.assertIn("12 saat", answer)
        self.assertIn("2 saat", answer)

    @patch("agent_loop.run_dated_capacity_tool")
    def test_missing_daily_data(self, dated_runner):
        dated_runner.return_value = {
            "ok": True,
            "data": {
                "required_skill": "backend",
                "required_hours": 14,
                "start_date": "2026-11-16",
                "end_date": "2026-11-18",
                "data_complete": False,
                "missing_availability": [
                    {"employee_id": "EMP-001",
                     "date": "2026-11-18"}
                ],
                "total_capacity": None,
                "shortage": None,
                "is_sufficient": None,
            },
        }

        call = SimpleNamespace(
            type="function_call",
            name="check_dated_capacity",
            arguments="{}",
            call_id="dated_call_2",
        )

        client = Mock()
        client.responses.create.side_effect = [
            SimpleNamespace(
                status="completed",
                output=[call],
                output_text="",
                usage=None,
            ),
            SimpleNamespace(
                status="completed",
                output=[],
                output_text="",
                usage=None,
            ),
        ]

        answer, _ = run_agent_turn(
            client=client,
            model_name="test-model",
            instructions="Test",
            tools=[],
            messages=[],
            run_policy_tool=Mock(),
        )

        self.assertIn("kesin hesaplanamadi", answer)
        self.assertNotIn("Mevcut kapasite:", answer)


if __name__ == "__main__":
    unittest.main()

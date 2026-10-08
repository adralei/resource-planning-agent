import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent_loop import MAX_TOOL_CALLS, run_agent_turn


def make_tool_response(index):
    call = SimpleNamespace(
        type="function_call",
        name="check_capacity",
        arguments='{"required_skill":"backend","required_hours":32}',
        call_id=f"call_{index}",
    )

    return SimpleNamespace(
        status="completed",
        output=[call],
        output_text="",
        usage=None,
    )


class TestAgentLoop(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.policy_runner = Mock()
        self.messages = [
            {"role": "user", "content": "Backend için 32 saat gerekiyor."}
        ]

    def run_turn(self):
        return run_agent_turn(
            client=self.client,
            model_name="test-model",
            instructions="Test talimatları",
            tools=[],
            messages=self.messages,
            run_policy_tool=self.policy_runner,
        )

    @patch("agent_loop.run_capacity_tool")
    def test_repeated_calls_stop_at_limit(self, capacity_runner):
        # Modelin aynı işlemi tekrar tekrar istediğini taklit ediyoruz.
        self.client.responses.create.side_effect = [
            make_tool_response(index)
            for index in range(MAX_TOOL_CALLS)
        ]

        capacity_runner.return_value = {
            "ok": True,
            "data": {
                "required_skill": "backend",
                "required_hours": 32,
                "total_capacity": 28,
                "shortage": 4,
                "is_sufficient": False,
                "candidates": ["Ada", "Bora"],
            },
        }

        text, responses = self.run_turn()

        self.assertEqual(capacity_runner.call_count, MAX_TOOL_CALLS)
        self.assertEqual(
            self.client.responses.create.call_count,
            MAX_TOOL_CALLS,
        )
        self.assertEqual(len(responses), MAX_TOOL_CALLS)
        self.assertIn("sınırına ulaşıldı", text)
        self.policy_runner.assert_not_called()

        outputs = [
            message
            for message in self.messages
            if isinstance(message, dict)
            and message.get("type") == "function_call_output"
        ]

        self.assertEqual(
            [output["call_id"] for output in outputs],
            [f"call_{index}" for index in range(MAX_TOOL_CALLS)],
        )

    @patch("agent_loop.run_capacity_tool")
    def test_tool_error_stops_loop(self, capacity_runner):
        self.client.responses.create.return_value = make_tool_response(0)

        capacity_runner.return_value = {
            "ok": False,
            "error": {
                "code": "invalid_arguments",
                "message": "Saat bilgisi geçersiz.",
            },
        }

        text, responses = self.run_turn()

        self.client.responses.create.assert_called_once()
        capacity_runner.assert_called_once()
        self.policy_runner.assert_not_called()
        self.assertEqual(len(responses), 1)
        self.assertIn("Saat bilgisi geçersiz.", text)
        self.assertNotIn("Mevcut kapasite:", text)


if __name__ == "__main__":
    unittest.main()
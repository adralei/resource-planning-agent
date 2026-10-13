import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent_loop import run_agent_turn


class TestCapacityErrorIntegration(unittest.TestCase):
    def test_invalid_capacity_arguments_stop_without_crashing(self):
        client = Mock()
        call = SimpleNamespace(
            type="function_call",
            name="check_capacity",
            arguments='{"required_skill":"backend","required_hours":-5}',
            call_id="invalid_capacity_call",
        )
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output=[call], output_text="", usage=None,
        )
        policy_runner = Mock()
        messages = [{"role": "user", "content": "Backend için -5 saat."}]

        # Model response is simulated; the real tool runner and validation run.
        with patch("capacity_tool.check_capacity") as calculation:
            text, responses = run_agent_turn(
                client=client,
                model_name="test-model",
                instructions="Test",
                tools=[],
                messages=messages,
                run_policy_tool=policy_runner,
            )

        calculation.assert_not_called()
        policy_runner.assert_not_called()
        client.responses.create.assert_called_once()
        self.assertEqual(len(responses), 1)
        self.assertIn("işlemi tamamlanamadı", text)
        self.assertNotIn("Mevcut kapasite:", text)
        output = json.loads(messages[-1]["output"])
        self.assertFalse(output["ok"])
        self.assertEqual(output["error"]["code"], "invalid_arguments")
        self.assertTrue(output["error"]["message"].strip())
        self.assertEqual(output["error"]["details"][0]["type"], "greater_than")


if __name__ == "__main__":
    unittest.main()

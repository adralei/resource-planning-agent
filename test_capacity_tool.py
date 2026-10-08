import unittest
from unittest.mock import patch

from pydantic import ValidationError

from capacity_tool import execute_capacity_tool


class TestCapacityTool(unittest.TestCase):
    def assert_rejected(self, arguments, expected_field, expected_type):
        # Gerçek kapasite fonksiyonunun yerine çağrıları izleyen
        # bir test nesnesi koyuyoruz.
        with patch("capacity_tool.check_capacity") as capacity_mock:
            with self.assertRaises(ValidationError) as caught:
                execute_capacity_tool(arguments)

            errors = caught.exception.errors()

            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0]["loc"], (expected_field,))
            self.assertEqual(errors[0]["type"], expected_type)

            # Hatalı girdiyle hesap yapılmamış olmalı.
            capacity_mock.assert_not_called()

    def test_valid_request_returns_shortage(self):
        result = execute_capacity_tool({
            "required_skill": "backend",
            "required_hours": 32,
        })

        self.assertEqual(result["total_capacity"], 28)
        self.assertEqual(result["shortage"], 4)
        self.assertFalse(result["is_sufficient"])

    def test_negative_hours_rejected(self):
        self.assert_rejected(
            {"required_skill": "backend", "required_hours": -5},
            "required_hours",
            "greater_than",
        )

    def test_text_hours_rejected(self):
        self.assert_rejected(
            {"required_skill": "backend", "required_hours": "32"},
            "required_hours",
            "int_type",
        )

    def test_unsupported_skill_rejected(self):
        self.assert_rejected(
            {"required_skill": "design", "required_hours": 8},
            "required_skill",
            "literal_error",
        )

    def test_missing_hours_rejected(self):
        self.assert_rejected(
            {"required_skill": "backend"},
            "required_hours",
            "missing",
        )

    def test_extra_field_rejected(self):
        self.assert_rejected(
            {
                "required_skill": "backend",
                "required_hours": 32,
                "approved": True,
            },
            "approved",
            "extra_forbidden",
        )
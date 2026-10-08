import unittest

from capacity_check import check_capacity


class TestCapacityCheck(unittest.TestCase):
    def setUp(self):
        # Her test aynı başlangıç verisiyle çalışır.
        self.employees = [
            {"name": "Ada", "skill": "backend", "available_hours": 16},
            {"name": "Bora", "skill": "backend", "available_hours": 12},
            {"name": "Cem", "skill": "devops", "available_hours": 8},
        ]

    def test_insufficient_capacity(self):
        result = check_capacity(self.employees, "backend", 32)

        self.assertEqual(result["total_capacity"], 28)
        self.assertEqual(result["shortage"], 4)
        self.assertFalse(result["is_sufficient"])

    def test_exact_capacity(self):
        result = check_capacity(self.employees, "devops", 8)

        self.assertEqual(result["total_capacity"], 8)
        self.assertEqual(result["shortage"], 0)
        self.assertTrue(result["is_sufficient"])

    def test_no_matching_employee(self):
        result = check_capacity(self.employees, "frontend", 10)

        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["total_capacity"], 0)
        self.assertEqual(result["shortage"], 10)
        self.assertFalse(result["is_sufficient"])

    def test_invalid_hours(self):
        for hours in [0, -5]:
            with self.subTest(hours=hours):
                with self.assertRaises(ValueError):
                    check_capacity(self.employees, "backend", hours)
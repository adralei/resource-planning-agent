import unittest

from policy_answer import PolicyAnswer, PolicyClaim, render_policy_answer


class TestPolicyAnswer(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {
                "id": "POL-003",
                "text": "Çalışanın mevcut ekip yöneticisinin onayı gerekir.",
            }
        ]

    def test_valid_claim_displays_source(self):
        answer = PolicyAnswer(
            status="answered",
            claims=[
                PolicyClaim(
                    text="Mevcut ekip yöneticisinin onayı gerekir.",
                    source_ids=["POL-003"],
                )
            ],
        )

        result = render_policy_answer(answer, self.sources)

        self.assertEqual(
            result,
            "Mevcut ekip yöneticisinin onayı gerekir. [POL-003]",
        )

    def test_source_not_retrieved_is_rejected(self):
        # POL-004 gerçek bir politika olsa bile bu turda getirilmedi.
        answer = PolicyAnswer(
            status="answered",
            claims=[
                PolicyClaim(
                    text="Hedef proje yöneticisinin onayı gerekir.",
                    source_ids=["POL-004"],
                )
            ],
        )

        with self.assertRaises(ValueError):
            render_policy_answer(answer, self.sources)

    def test_claim_without_source_is_rejected(self):
        answer = PolicyAnswer(
            status="answered",
            claims=[
                PolicyClaim(
                    text="Yönetici iki gün içinde cevap vermelidir.",
                    source_ids=[],
                )
            ],
        )

        with self.assertRaises(ValueError):
            render_policy_answer(answer, self.sources)

    def test_insufficient_with_claims_is_rejected(self):
        # "Yeterli bilgi yok" durumu ile iddia listesi çelişiyor.
        answer = PolicyAnswer(
            status="insufficient",
            claims=[
                PolicyClaim(
                    text="Mevcut ekip yöneticisinin onayı gerekir.",
                    source_ids=["POL-003"],
                )
            ],
        )

        with self.assertRaises(ValueError):
            render_policy_answer(answer, self.sources)

    def test_partial_answer_preserves_claim_and_marks_missing_info(self):
        answer = PolicyAnswer(
            status="partial",
            claims=[
                PolicyClaim(
                    text="Mevcut ekip yöneticisinin onayı gerekir.",
                    source_ids=["POL-003"],
                )
            ],
        )

        result = render_policy_answer(answer, self.sources)

        self.assertIn(
            "Mevcut ekip yöneticisinin onayı gerekir. [POL-003]",
            result,
        )
        self.assertIn(
            "Sorunuzun kalan kısmını cevaplamak için",
            result,
        )


if __name__ == "__main__":
    unittest.main()

import hashlib
import hmac
import json


FINGERPRINT_VERSION = "dated-plan-v1"

PROTECTED_FIELDS = (
    "plan_id",
    "project_id",
    "planning_period",
    "proposal",
    "required_approvals",
)


def build_approval_payload(plan):
    """
    Onay kapsamindaki plan alanlarini ayirir.

    Sonradan degisebilen uygulama durumu veya
    islem zamani gibi alanlar bu ozete dahil edilmez.
    """

    if not isinstance(plan, dict):
        raise ValueError("Plan bir nesne olmali.")

    for field in PROTECTED_FIELDS:
        if field not in plan:
            raise ValueError(
                f"Korunan plan alani eksik: {field}"
            )

    if not isinstance(plan["proposal"], dict):
        raise ValueError("Plan onerisi gecersiz.")

    if not isinstance(plan["required_approvals"], list):
        raise ValueError("Onay listesi gecersiz.")

    return {
        "fingerprint_version": FINGERPRINT_VERSION,
        **{
            field: plan[field]
            for field in PROTECTED_FIELDS
        },
    }


def calculate_plan_fingerprint(plan):
    """
    Planin korunan iceriginden SHA-256 ozeti uretir.
    """

    payload = build_approval_payload(plan)

    try:
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Plan fingerprint icin JSON'a "
            "donusturulemedi."
        ) from error

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()


def verify_plan_fingerprint(plan, expected_fingerprint):
    """
    Mevcut plan ozeti ile onay aninda
    kaydedilmis guvenilir ozeti karsilastirir.
    """

    if (
        not isinstance(expected_fingerprint, str)
        or len(expected_fingerprint) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_fingerprint
        )
    ):
        raise ValueError("Gecersiz fingerprint.")

    actual_fingerprint = calculate_plan_fingerprint(plan)

    return hmac.compare_digest(
        actual_fingerprint,
        expected_fingerprint,
    )

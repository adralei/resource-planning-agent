
from resource_planning_agent.approvals.approval_consistency import (
    inspect_approval_consistency,
)


RECOVERY_POLICIES = {
    "consistent": {
        "action": "continue_to_preflight",
        "manual_review_required": False,
        "reason": (
            "Onay kayitlari tutarli. "
            "Normal preflight kontrollerine devam edilebilir."
        ),
    },
    "missing_registry": {
        "action": "investigate_approval_evidence",
        "manual_review_required": True,
        "reason": (
            "Bagimsiz onay kaydi eksik. "
            "JSON verisinden otomatik kayit olusturulamaz."
        ),
    },
    "fingerprint_mismatch": {
        "action": "investigate_integrity_violation",
        "manual_review_required": True,
        "reason": (
            "Onaylanan icerikle mevcut kayitlar uyusmuyor. "
            "Plan uygulamasi durdurulmali."
        ),
    },
    "missing_fingerprint": {
        "action": "investigate_missing_fingerprint",
        "manual_review_required": True,
        "reason": (
            "Onay fingerprint'i eksik. "
            "Guvenilir onay kaniti incelenmeli."
        ),
    },
    "not_approved": {
        "action": "complete_normal_approval_workflow",
        "manual_review_required": False,
        "reason": (
            "Plan henuz onayli degil. "
            "Normal onay sureci tamamlanmali."
        ),
    },
    "invalid_plan": {
        "action": "investigate_invalid_plan",
        "manual_review_required": True,
        "reason": (
            "Plan yapisi veya onay kapsami gecersiz. "
            "Veri butunlugu incelenmeli."
        ),
    },
}


def assess_approval_recovery(plan_id):
    """
    Onay tutarsizligi icin guvenli kurtarma karari uretir.

    - Veritabanina yazmaz.
    - Eksik fingerprint olusturmaz.
    - Onay durumunu degistirmez.
    - Rezervasyon yapmaz.
    """

    inspection = inspect_approval_consistency(plan_id)

    status = inspection.get("status")

    if status not in RECOVERY_POLICIES:
        raise ValueError(
            f"Bilinmeyen approval consistency durumu: {status}"
        )

    policy = RECOVERY_POLICIES[status]

    consistent = (
        status == "consistent"
        and inspection.get("consistent") is True
    )

    if status == "consistent" and not consistent:
        raise ValueError(
            "Consistency raporu kendi icinde celisiyor."
        )

    return {
        "plan_id": inspection["plan_id"],
        "consistency_status": status,
        "recommended_action": policy["action"],
        "reason": policy["reason"],
        "manual_review_required": (
            policy["manual_review_required"]
        ),
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": consistent,
        "recovered": False,
    }

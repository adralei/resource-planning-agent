
from datetime import datetime, timezone
from uuid import uuid4

from resource_planning_agent.approvals.approval_recovery import (
    assess_approval_recovery,
)


REVIEWABLE_STATUSES = {
    "missing_registry",
    "fingerprint_mismatch",
    "missing_fingerprint",
    "invalid_plan",
}


def prepare_approval_review_case(plan_id):
    """
    Tutarsiz planlar icin manuel inceleme paketi hazirlar.

    Bu fonksiyon:
    - Plan durumunu degistirmez.
    - Eksik onay kaydi olusturmaz.
    - Fingerprint yeniden yazmaz.
    - Rezervasyon yapmaz.
    - Inceleme paketini kalici olarak kaydetmez.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    assessment = assess_approval_recovery(plan_id)

    if not isinstance(assessment, dict):
        raise ValueError("Recovery raporu gecersiz.")

    if assessment.get("plan_id") != plan_id:
        raise ValueError("Recovery plan kimligi uyusmuyor.")

    status = assessment.get("consistency_status")

    if status not in REVIEWABLE_STATUSES:
        raise ValueError(
            "Bu plan manuel recovery incelemesine uygun degil."
        )

    if (
        assessment.get("manual_review_required") is not True
        or assessment.get("can_proceed_to_preflight") is not False
        or assessment.get("automatic_recovery_allowed") is not False
    ):
        raise ValueError(
            "Recovery raporunda guvenlik celiskisi var."
        )

    return {
        "case_id": str(uuid4()),
        "plan_id": plan_id,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "case_status": "awaiting_manual_review",
        "consistency_status": status,
        "recommended_action": assessment["recommended_action"],
        "reason": assessment["reason"],
        "required_evidence": [
            "Original approval records",
            "Authorized approver identities",
            "Approved allocation snapshot",
            "Approval timestamps",
            "Registry and storage error logs",
        ],
        "review_steps": [
            "Investigate the inconsistency",
            "Collect independent approval evidence",
            "Verify approver authorization",
            "Compare the approved plan content",
            "Determine whether a new approval workflow is required",
        ],
        "manual_review_required": True,
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": False,
        "approval_granted": False,
        "registry_modified": False,
        "reservations_created": False,
    }

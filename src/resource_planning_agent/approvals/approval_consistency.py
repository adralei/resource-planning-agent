
from resource_planning_agent.storage.plan_store import (
    load_plan,
)
from resource_planning_agent.storage.approval_registry import (
    read_approval_fingerprint,
)
from resource_planning_agent.planning.plan_fingerprint import (
    verify_plan_fingerprint,
)
from resource_planning_agent.planning.dated_plan_guard import (
    validate_approved_dated_plan,
)


def inspect_approval_consistency(plan_id):
    """
    Tarihli planin JSON ve SQLite onay kayitlarini
    salt-okunur olarak inceler.

    Eksik kayitlari otomatik olusturmaz.
    Onay vermez ve rezervasyon yapmaz.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    plan = load_plan(plan_id)

    if not isinstance(plan, dict):
        raise ValueError("Plan verisi gecersiz.")

    if plan.get("plan_id") != plan_id:
        raise ValueError("Plan kimligi eslesmiyor.")

    result = {
        "plan_id": plan_id,
        "status": None,
        "consistent": False,
        "requires_manual_review": False,
        "message": "",
    }

    proposal = plan.get("proposal")

    if not isinstance(proposal, dict):
        result["status"] = "invalid_plan"
        result["requires_manual_review"] = True
        result["message"] = "Plan onerisi gecersiz."
        return result

    reservations = proposal.get("dated_reservations")

    if not isinstance(reservations, list) or not reservations:
        result["status"] = "invalid_plan"
        result["requires_manual_review"] = True
        result["message"] = (
            "Tarihli rezervasyonlar bulunamadi."
        )
        return result

    if plan.get("status") != "approved":
        result["status"] = "not_approved"
        result["message"] = (
            "Plan henuz nihai onay almamis."
        )
        return result

    try:
        validate_approved_dated_plan(
            plan,
            reservations,
        )
    except (ValueError, KeyError, TypeError) as error:
        result["status"] = "invalid_plan"
        result["requires_manual_review"] = True
        result["message"] = (
            f"Onay kapsami gecersiz: {error}"
        )
        return result

    fingerprint = plan.get("approval_fingerprint")

    if fingerprint is None:
        result["status"] = "missing_fingerprint"
        result["requires_manual_review"] = True
        result["message"] = (
            "Plan JSON fingerprint'i bulunamadi."
        )
        return result

    try:
        fingerprint_valid = verify_plan_fingerprint(
            plan,
            fingerprint,
        )
    except ValueError:
        fingerprint_valid = False

    if not fingerprint_valid:
        result["status"] = "fingerprint_mismatch"
        result["requires_manual_review"] = True
        result["message"] = (
            "Plan icerigi JSON fingerprint'i ile "
            "eslesmiyor."
        )
        return result

    # Registry erisim hatalari gizlenmez.
    # SQLite hatasi, kayit eksikligi demek degildir.
    registered = read_approval_fingerprint(plan_id)

    if registered is None:
        result["status"] = "missing_registry"
        result["requires_manual_review"] = True
        result["message"] = (
            "Plan onayli fakat bagimsiz SQLite "
            "onay kaydi eksik."
        )
        return result

    if registered.get("fingerprint") != fingerprint:
        result["status"] = "fingerprint_mismatch"
        result["requires_manual_review"] = True
        result["message"] = (
            "JSON ve SQLite fingerprint'leri "
            "eslesmiyor."
        )
        return result

    result["status"] = "consistent"
    result["consistent"] = True
    result["message"] = (
        "Onay ve fingerprint kayitlari tutarli."
    )

    return result

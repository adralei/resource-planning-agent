
from resource_planning_agent.storage.plan_store import load_plan
from resource_planning_agent.planning.dated_plan_guard import validate_approved_dated_plan


def preflight_dated_plan(plan_id):
    """
    Kaydedilmis tarihli plani yukler ve
    rezervasyon kapsamini dogrular.

    Rezervasyon veya kapasite degisikligi yapmaz.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    plan = load_plan(plan_id)

    proposal = plan.get("proposal")
    if not isinstance(proposal, dict):
        raise ValueError("Plan onerisi gecersiz.")

    reservations = proposal.get("dated_reservations")

    if not isinstance(reservations, list) or not reservations:
        raise ValueError(
            "Planda tarihli rezervasyonlar bulunmuyor."
        )

    validation = validate_approved_dated_plan(
        plan,
        reservations,
    )

    return {
        "status": "preflight_passed",
        "plan_id": plan["plan_id"],
        "project_id": plan["project_id"],
        "reservation_count": validation["reservation_count"],
        "reservations": reservations,
        "ready_for_capacity_revalidation": True,
        "applied": False,
    }

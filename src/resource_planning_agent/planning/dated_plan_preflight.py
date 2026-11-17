
from resource_planning_agent.storage.plan_store import load_plan
from resource_planning_agent.planning.dated_plan_guard import validate_approved_dated_plan

from resource_planning_agent.planning.plan_fingerprint import (
    verify_plan_fingerprint,
)

from resource_planning_agent.storage.approval_registry import (
    verify_registered_approval,
)

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


    # Tarihli planlar icin onay fingerprint'i zorunlu.
    expected_fingerprint = plan.get(
        "approval_fingerprint"
    )

    if expected_fingerprint is None:
        raise ValueError(
            "Onay fingerprint'i bulunamadi. "
            "Plan uygulamaya hazir degil."
        )

    if not verify_plan_fingerprint(
        plan,
        expected_fingerprint,
    ):
        raise ValueError(
            "Plan icerigi onay sonrasinda "
            "degismis veya fingerprint eslesmiyor."
        )


    # Plan JSON'undaki fingerprint tek basina yeterli degil.
    # SQLite'daki bagimsiz onay kaydi da eslesmeli.
    if not verify_registered_approval(plan):
        raise ValueError(
            "Bagimsiz onay kaydi bulunamadi "
            "veya plan icerigi kayitla eslesmiyor."
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

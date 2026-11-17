
from resource_planning_agent.storage.plan_store import load_plan

from resource_planning_agent.planning.dated_plan_guard import (
    validate_approved_dated_plan,
)

from resource_planning_agent.planning.plan_fingerprint import (
    verify_plan_fingerprint,
)

from resource_planning_agent.storage.approval_registry import (
    verify_registered_approval,
)


def preflight_dated_plan(plan_id):
    """
    Kaydedilmis tarihli plani yukler ve dogrular.

    Kontroller:
    1. Plan kimligi
    2. Tarihli rezervasyonlar
    3. Planin onay durumu ve onay kapsami
    4. Plan fingerprint dogrulamasi
    5. Bagimsiz SQLite onay kaydi

    Bu fonksiyon rezervasyon olusturmaz
    veya kapasiteyi degistirmez.
    """

    # 1. Plan kimligini dogrula.
    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    # 2. Kaydedilmis plani yukle.
    plan = load_plan(plan_id)

    if not isinstance(plan, dict):
        raise ValueError("Plan verisi gecersiz.")

    proposal = plan.get("proposal")

    if not isinstance(proposal, dict):
        raise ValueError("Plan onerisi gecersiz.")

    reservations = proposal.get("dated_reservations")

    if not isinstance(reservations, list) or not reservations:
        raise ValueError(
            "Planda tarihli rezervasyonlar bulunmuyor."
        )

    # 3. Onay ve rezervasyon kapsamini dogrula.
    validation = validate_approved_dated_plan(
        plan,
        reservations,
    )

    # 4. Planin kendi fingerprint'ini dogrula.
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

    # 5. SQLite'daki bagimsiz onay kaydini dogrula.
    if not verify_registered_approval(plan):
        raise ValueError(
            "Bagimsiz onay kaydi bulunamadi "
            "veya plan icerigi kayitla eslesmiyor."
        )

    # 6. Tum kontroller basarili.
    return {
        "status": "preflight_passed",
        "plan_id": plan["plan_id"],
        "project_id": plan["project_id"],
        "reservation_count": validation["reservation_count"],
        "reservations": reservations,
        "ready_for_capacity_revalidation": True,
        "applied": False,
    }

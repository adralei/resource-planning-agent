
import re

from resource_planning_agent.storage.database import (
    PLANNING_PERIOD,
)

from resource_planning_agent.storage.dated_application_registry import (
    initialize_dated_application_registry,
)

from resource_planning_agent.planning.dated_plan_preflight import (
    preflight_dated_plan,
)

from resource_planning_agent.planning.dated_reservations import (
    initialize_reservation_schema,
    reserve_daily_batch,
)


def apply_approved_dated_plan(plan_id):
    """
    Onaylanmis tarihli planin rezervasyonlarini
    ve uygulama kaydini atomik olarak olusturur.

    Preflight:
        Plan ve onay butunlugunu dogrular.

    SQLite transaction:
        Onay fingerprint'ini tekrar kontrol eder.
        Guncel kapasiteyi kontrol eder.
        Rezervasyonlari kaydeder.
        Application Registry kaydini olusturur.

    JSON plan durumunu degistirmez.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    # Onay ve JSON butunlugu burada dogrulanir.
    preflight = preflight_dated_plan(plan_id)

    if (
        not isinstance(preflight, dict)
        or preflight.get("status") != "preflight_passed"
        or preflight.get("plan_id") != plan_id
        or preflight.get("ready_for_capacity_revalidation")
            is not True
        or preflight.get("applied") is not False
    ):
        raise ValueError("Preflight sonucu gecersiz.")

    reservations = preflight.get("reservations")

    if not isinstance(reservations, list) or not reservations:
        raise ValueError("Rezervasyon listesi gecersiz.")

    if (
        type(preflight.get("reservation_count")) is not int
        or preflight["reservation_count"] != len(reservations)
    ):
        raise ValueError("Rezervasyon sayisi uyusmuyor.")

    approval_fingerprint = preflight.get(
        "approval_fingerprint"
    )

    if (
        not isinstance(approval_fingerprint, str)
        or re.fullmatch(
            r"[0-9a-f]{64}",
            approval_fingerprint,
        ) is None
    ):
        raise ValueError(
            "Preflight fingerprint'i gecersiz."
        )

    project_id = preflight.get("project_id")

    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("Preflight project_id gecersiz.")

    # Sema olusturma islemleri transaction'dan once.
    initialize_reservation_schema()
    initialize_dated_application_registry()

    # Bu cagrida approval_fingerprint verilmesi,
    # rezervasyon motorunun atomik uygulama modunu acar.
    result = reserve_daily_batch(
        plan_id=plan_id,
        reservations=reservations,
        planning_period=PLANNING_PERIOD,
        approval_fingerprint=approval_fingerprint,
    )

    if (
        not isinstance(result, dict)
        or result.get("success") is not True
        or result.get("plan_id") != plan_id
        or result.get("reservation_count") != len(reservations)
    ):
        raise RuntimeError(
            "Batch reservation sonucu gecersiz."
        )

    return {
        "status": "reservations_applied",
        "plan_id": plan_id,
        "project_id": project_id,
        "approval_fingerprint": approval_fingerprint,
        "reservation_count": result["reservation_count"],
        "total_reserved_hours": result["total_reserved_hours"],
        "reservation_ids": result["reservation_ids"],
        "reservations_committed": True,
        "application_record_created": True,
    }

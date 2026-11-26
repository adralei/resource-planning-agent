
from resource_planning_agent.storage.database import (
    PLANNING_PERIOD,
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
    Onaylanmis tarihli plani gunluk rezervasyonlara uygular.

    1. Plan onayini ve fingerprint'i dogrular.
    2. Rezervasyon tablosunu hazirlar.
    3. Tum rezervasyonlari tek SQLite transaction
       icinde kapasite kontroluyle kaydeder.

    Basarisiz rezervasyon batch'i rollback edilir.

    Bu ilk surum JSON plan durumunu degistirmez.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    # Onay veya registry dogrulanamazsa burada dur.
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

    if preflight.get("reservation_count") != len(reservations):
        raise ValueError("Rezervasyon sayisi uyusmuyor.")

    # Semayi hazirla. Bu fonksiyon rezervasyon eklemez.
    initialize_reservation_schema()

    # reserve_daily_batch mevcut kapasiteyi kendi
    # transaction'i icinde tekrar kontrol eder.
    # Hata olursa hicbir rezervasyon kaydedilmez.
    result = reserve_daily_batch(
        plan_id=plan_id,
        reservations=reservations,
        planning_period=PLANNING_PERIOD,
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
        "project_id": preflight["project_id"],
        "reservation_count": result["reservation_count"],
        "total_reserved_hours": result["total_reserved_hours"],
        "reservation_ids": result["reservation_ids"],
        "reservations_committed": True,
    }

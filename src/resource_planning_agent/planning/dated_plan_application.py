
import copy
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

from resource_planning_agent.planning.dated_plan_snapshot import (
    revalidate_dated_plan_snapshot,
)

from resource_planning_agent.planning.dated_reservations import (
    initialize_reservation_schema,
    reserve_daily_batch,
)


def apply_approved_dated_plan(plan_id):
    """
    Onaylanmis tarihli plani atomik olarak uygular.

    1. Ilk Preflight dogrulamasi.
    2. Snapshot yeniden dogrulamasi.
    3. SQLite icinde onay ve kapasite kontrolu.
    4. Rezervasyonlar ve Application Registry commit.

    JSON plan dosyasini degistirmez.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    # Ilk Preflight plan ve onay butunlugunu kontrol eder.
    preflight = preflight_dated_plan(plan_id)

    if not isinstance(preflight, dict):
        raise ValueError("Preflight sonucu gecersiz.")

    # Ilk goruntuyu bagimsiz bir kopya olarak sakla.
    initial = copy.deepcopy(preflight)

    if (
        initial.get("status") != "preflight_passed"
        or initial.get("plan_id") != plan_id
        or initial.get("ready_for_capacity_revalidation")
            is not True
        or initial.get("applied") is not False
    ):
        raise ValueError("Preflight sonucu gecersiz.")

    reservations = initial.get("reservations")

    if not isinstance(reservations, list) or not reservations:
        raise ValueError("Rezervasyon listesi gecersiz.")

    if (
        type(initial.get("reservation_count")) is not int
        or initial["reservation_count"] != len(reservations)
    ):
        raise ValueError("Rezervasyon sayisi uyusmuyor.")

    fingerprint = initial.get("approval_fingerprint")

    if (
        not isinstance(fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
    ):
        raise ValueError(
            "Preflight fingerprint'i gecersiz."
        )

    project_id = initial.get("project_id")

    if (
        not isinstance(project_id, str)
        or not project_id.strip()
    ):
        raise ValueError("Preflight project_id gecersiz.")

    # Ikinci Preflight: plan yeniden okunur.
    # Degisiklik varsa bu fonksiyon hata verir.
    snapshot = revalidate_dated_plan_snapshot(
        initial
    )

    if (
        not isinstance(snapshot, dict)
        or snapshot.get("status") != "snapshot_revalidated"
        or snapshot.get("snapshot_matches") is not True
        or snapshot.get("applied") is not False
        or snapshot.get("plan_id") != plan_id
        or snapshot.get("project_id") != project_id
        or snapshot.get("approval_fingerprint") != fingerprint
        or type(snapshot.get("reservation_count")) is not int
        or snapshot["reservation_count"] != len(reservations)
        or snapshot.get("reservations") != reservations
    ):
        raise ValueError(
            "Snapshot revalidation sonucu gecersiz."
        )

    # Yalnizca ikinci kontrol basariliysa
    # veritabani uygulama asamasina ilerle.
    initialize_reservation_schema()
    initialize_dated_application_registry()

    # SQLite transaction icinde:
    # - Approval Registry tekrar kontrol edilir.
    # - Guncel kapasite tekrar kontrol edilir.
    # - Rezervasyonlar eklenir.
    # - Application Registry kaydi eklenir.
    result = reserve_daily_batch(
        plan_id=plan_id,
        reservations=copy.deepcopy(
            snapshot["reservations"]
        ),
        planning_period=PLANNING_PERIOD,
        approval_fingerprint=fingerprint,
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
        "approval_fingerprint": fingerprint,
        "reservation_count": result["reservation_count"],
        "total_reserved_hours": result["total_reserved_hours"],
        "reservation_ids": result["reservation_ids"],
        "reservations_committed": True,
        "application_record_created": True,
        "snapshot_revalidated": True,
    }

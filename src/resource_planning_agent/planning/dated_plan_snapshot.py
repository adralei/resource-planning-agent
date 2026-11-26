
import copy
import json
import re

from resource_planning_agent.planning.dated_plan_preflight import (
    preflight_dated_plan,
)


def _validate_snapshot(snapshot):
    """
    Preflight sonucunun beklenen sozlesmeye
    uygun oldugunu kontrol eder.
    """

    if not isinstance(snapshot, dict):
        raise ValueError("Preflight snapshot gecersiz.")

    if (
        snapshot.get("status") != "preflight_passed"
        or snapshot.get("ready_for_capacity_revalidation")
        is not True
        or snapshot.get("applied") is not False
    ):
        raise ValueError(
            "Preflight snapshot basarili durumda degil."
        )

    for field in ("plan_id", "project_id"):
        value = snapshot.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Snapshot alani gecersiz: {field}"
            )

    fingerprint = snapshot.get("approval_fingerprint")

    if (
        not isinstance(fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
    ):
        raise ValueError(
            "Snapshot approval fingerprint gecersiz."
        )

    reservations = snapshot.get("reservations")
    reservation_count = snapshot.get("reservation_count")

    if (
        not isinstance(reservations, list)
        or not reservations
        or type(reservation_count) is not int
        or reservation_count != len(reservations)
    ):
        raise ValueError(
            "Snapshot rezervasyon bilgileri gecersiz."
        )

    return snapshot


def _canonical_snapshot(snapshot):
    """
    Karsilastirilacak alanlarin deterministik
    JSON gosterimini olusturur.

    Ek metadata alanlari karsilastirmaya dahil edilmez.
    """

    fields = (
        "status",
        "plan_id",
        "project_id",
        "reservation_count",
        "reservations",
        "approval_fingerprint",
        "ready_for_capacity_revalidation",
        "applied",
    )

    selected = {
        field: snapshot[field]
        for field in fields
    }

    try:
        return json.dumps(
            selected,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Snapshot karsilastirma verisi gecersiz."
        ) from error


def revalidate_dated_plan_snapshot(initial_preflight):
    """
    Plani yeniden preflight kontrolunden gecirir.

    Ilk snapshot ile guncel dogrulama sonucunu
    karsilastirir.

    Plan veya rezervasyonlari degistirmez.
    SQLite transaction baslatmaz.
    """

    # Ilk sonucu sabitle: daha sonraki bir islem
    # ayni sozluk/list nesnesini degistirmesin.
    initial = copy.deepcopy(initial_preflight)

    _validate_snapshot(initial)

    # Ikinci Preflight plan dosyasini yeniden okur,
    # approval ve fingerprint kontrollerini tekrar yapar.
    current = preflight_dated_plan(initial["plan_id"])

    _validate_snapshot(current)

    if (
        _canonical_snapshot(initial)
        != _canonical_snapshot(current)
    ):
        raise ValueError(
            "Plan snapshot degisti. "
            "Uygulama icin yeniden onay "
            "veya inceleme gerekebilir."
        )

    return {
        "status": "snapshot_revalidated",
        "plan_id": initial["plan_id"],
        "project_id": initial["project_id"],
        "approval_fingerprint": (
            initial["approval_fingerprint"]
        ),
        "reservation_count": initial["reservation_count"],
        "reservations": copy.deepcopy(
            initial["reservations"]
        ),
        "snapshot_matches": True,
        "applied": False,
    }

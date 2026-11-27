
from collections import Counter
from contextlib import closing

from resource_planning_agent.storage.database import (
    connect_db,
    PLANNING_PERIOD,
)

from resource_planning_agent.planning.dated_plan_preflight import (
    preflight_dated_plan,
)


def _expected_reservation_counter(reservations):
    """
    Onaylanmis rezervasyon listesini karsilastirma
    icin normalize eder.
    """

    if not isinstance(reservations, list) or not reservations:
        raise ValueError("Rezervasyon listesi gecersiz.")

    expected = Counter()
    seen_ids = set()

    for item in reservations:
        if not isinstance(item, dict):
            raise ValueError("Rezervasyon verisi gecersiz.")

        reservation_id = item.get("reservation_id")
        employee_id = item.get("employee_id")
        capacity_date = item.get("capacity_date")
        hours = item.get("reserved_hours")

        for value in (
            reservation_id,
            employee_id,
            capacity_date,
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Rezervasyon alani gecersiz.")

        if type(hours) is not int or hours <= 0:
            raise ValueError("Rezervasyon saati gecersiz.")

        if reservation_id in seen_ids:
            raise ValueError("Tekrarlanan reservation_id.")

        seen_ids.add(reservation_id)

        expected[(
            reservation_id,
            employee_id,
            PLANNING_PERIOD,
            capacity_date,
            hours,
        )] += 1

    return expected


def confirm_dated_plan_application(plan_id):
    """
    Tarihli planin daha once uygulanip
    uygulanmadigini dogrular.

    - Preflight tekrar calisir.
    - Application Registry ve rezervasyonlar
      ayni SQLite okuma transaction'inda incelenir.
    - Yeni rezervasyon veya onay olusturmaz.
    - Tutarsiz kayitlari basarili saymaz.

    Donus durumu:
      confirmed_applied
      not_applied

    Tutarsizlik varsa ValueError olusur.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    preflight = preflight_dated_plan(plan_id)

    if (
        not isinstance(preflight, dict)
        or preflight.get("status") != "preflight_passed"
        or preflight.get("plan_id") != plan_id
        or preflight.get("applied") is not False
        or preflight.get(
            "ready_for_capacity_revalidation"
        ) is not True
    ):
        raise ValueError("Preflight sonucu gecersiz.")

    fingerprint = preflight.get("approval_fingerprint")

    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(c not in "0123456789abcdef" for c in fingerprint)
    ):
        raise ValueError("Approval fingerprint gecersiz.")

    reservations = preflight.get("reservations")

    expected = _expected_reservation_counter(reservations)

    if (
        type(preflight.get("reservation_count")) is not int
        or preflight["reservation_count"] != len(reservations)
    ):
        raise ValueError("Rezervasyon sayisi uyusmuyor.")

    with closing(connect_db()) as connection:
        # Iki tablodaki verileri tutarli bir SQLite
        # okuma snapshot'i uzerinden inceliyoruz.
        connection.execute("BEGIN")

        try:
            application = connection.execute("""
                SELECT
                    plan_id,
                    approval_fingerprint,
                    reservation_count,
                    applied_at
                FROM dated_plan_applications
                WHERE plan_id = ?
            """, (plan_id,)).fetchone()

            rows = connection.execute("""
                SELECT
                    reservation_id,
                    employee_id,
                    planning_period,
                    capacity_date,
                    reserved_hours
                FROM daily_reservations
                WHERE plan_id = ?
            """, (plan_id,)).fetchall()

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    if application is None:
        if rows:
            raise ValueError(
                "Application Registry eksik fakat "
                "plana ait rezervasyonlar mevcut."
            )

        return {
            "status": "not_applied",
            "plan_id": plan_id,
            "confirmed": False,
            "safe_to_retry": True,
            "reservation_count": 0,
        }

    if (
        application["approval_fingerprint"] != fingerprint
        or application["reservation_count"] != len(reservations)
    ):
        raise ValueError(
            "Application Registry onaylanan "
            "planla eslesmiyor."
        )

    actual = Counter(
        (
            row["reservation_id"],
            row["employee_id"],
            row["planning_period"],
            row["capacity_date"],
            row["reserved_hours"],
        )
        for row in rows
    )

    if actual != expected:
        raise ValueError(
            "Kaydedilmis rezervasyonlar onaylanan "
            "planla eslesmiyor."
        )

    return {
        "status": "confirmed_applied",
        "plan_id": plan_id,
        "confirmed": True,
        "safe_to_retry": False,
        "reservation_count": len(rows),
        "approval_fingerprint": fingerprint,
        "applied_at": application["applied_at"],
    }

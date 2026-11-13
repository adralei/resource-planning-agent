
"""Initialize and read daily employee reservation records."""

from contextlib import closing

from database import connect_db
from dated_capacity import initialize_daily_capacity_schema

from database import PLANNING_PERIOD
from dated_capacity import _parse_iso_date


def initialize_reservation_schema():
    """
    Gunluk kaynak rezervasyon tablosunu olusturur.

    Bu fonksiyon:
    - Rezervasyon yapmaz.
    - Mevcut kapasiteyi degistirmez.
    - Mevcut rezervasyonlari silmez.
    """

    initialize_daily_capacity_schema()

    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS daily_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    employee_id TEXT NOT NULL,
                    planning_period TEXT NOT NULL,
                    capacity_date TEXT NOT NULL,
                    reserved_hours INTEGER NOT NULL
                        CHECK (
                            typeof(reserved_hours) = 'integer'
                            AND reserved_hours > 0
                        ),

                    FOREIGN KEY (
                        employee_id,
                        planning_period,
                        capacity_date
                    )
                    REFERENCES employee_daily_capacity (
                        employee_id,
                        planning_period,
                        capacity_date
                    )
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_daily_reservations_employee_date
                ON daily_reservations (
                    employee_id,
                    planning_period,
                    capacity_date
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_daily_reservations_plan
                ON daily_reservations (plan_id)
            """)

            connection.commit()

        except Exception:
            connection.rollback()
            raise


def get_daily_reservations(
    employee_id,
    capacity_date,
    planning_period,
):
    """
    Belirli bir calisanin belirli gundeki
    rezervasyonlarini getirir.
    """

    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT
                reservation_id,
                plan_id,
                employee_id,
                capacity_date,
                reserved_hours
            FROM daily_reservations
            WHERE employee_id = ?
              AND planning_period = ?
              AND capacity_date = ?
            ORDER BY reservation_id
        """, (
            employee_id,
            planning_period,
            capacity_date,
        )).fetchall()

    return [dict(row) for row in rows]


def reserve_daily_hours(
    reservation_id,
    plan_id,
    employee_id,
    capacity_date,
    reserved_hours,
    planning_period=PLANNING_PERIOD,
):
    """
    Bir calisanin belirli gundeki kapasitesini rezerve eder.

    Kapasite kontrolu ve INSERT ayni transaction
    icinde gerceklestirilir.
    """

    for field, value in (
        ("reservation_id", reservation_id),
        ("plan_id", plan_id),
        ("employee_id", employee_id),
        ("planning_period", planning_period),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} bos olamaz.")

    _parse_iso_date(capacity_date, "capacity_date")

    if type(reserved_hours) is not int or reserved_hours <= 0:
        raise ValueError(
            "reserved_hours pozitif tam sayi olmali."
        )

    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            duplicate = connection.execute("""
                SELECT 1
                FROM daily_reservations
                WHERE reservation_id = ?
            """, (reservation_id,)).fetchone()

            if duplicate is not None:
                raise ValueError(
                    "Bu reservation_id zaten kullaniliyor."
                )

            capacity = connection.execute("""
                SELECT available_hours
                FROM employee_daily_capacity
                WHERE employee_id = ?
                  AND planning_period = ?
                  AND capacity_date = ?
            """, (
                employee_id,
                planning_period,
                capacity_date,
            )).fetchone()

            if capacity is None:
                raise ValueError(
                    "Bu calisan ve tarih icin gunluk "
                    "kapasite kaydi bulunamadi."
                )

            reserved = connection.execute("""
                SELECT COALESCE(
                    SUM(reserved_hours), 0
                ) AS total_reserved
                FROM daily_reservations
                WHERE employee_id = ?
                  AND planning_period = ?
                  AND capacity_date = ?
            """, (
                employee_id,
                planning_period,
                capacity_date,
            )).fetchone()["total_reserved"]

            remaining = capacity["available_hours"] - reserved

            if reserved_hours > remaining:
                raise ValueError(
                    "Yetersiz gunluk kapasite. "
                    f"Kalan: {remaining} saat, "
                    f"istenen: {reserved_hours} saat."
                )

            connection.execute("""
                INSERT INTO daily_reservations (
                    reservation_id,
                    plan_id,
                    employee_id,
                    planning_period,
                    capacity_date,
                    reserved_hours
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                reservation_id,
                plan_id,
                employee_id,
                planning_period,
                capacity_date,
                reserved_hours,
            ))

            connection.commit()

            return {
                "success": True,
                "reservation_id": reservation_id,
                "plan_id": plan_id,
                "employee_id": employee_id,
                "capacity_date": capacity_date,
                "reserved_hours": reserved_hours,
                "remaining_hours": remaining - reserved_hours,
            }

        except Exception:
            connection.rollback()
            raise



def reserve_daily_batch(
    plan_id,
    reservations,
    planning_period=PLANNING_PERIOD,
):
    """
    Bir plana ait birden fazla gunluk rezervasyonu
    tek transaction icinde olusturur.

    Basarisiz herhangi bir islem tum batch'i
    geri alir.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("plan_id bos olamaz.")

    if (
        not isinstance(planning_period, str)
        or not planning_period.strip()
    ):
        raise ValueError("planning_period bos olamaz.")

    if not isinstance(reservations, list) or not reservations:
        raise ValueError(
            "reservations bos olmayan bir liste olmali."
        )

    required_fields = {
        "reservation_id",
        "employee_id",
        "capacity_date",
        "reserved_hours",
    }

    seen_ids = set()
    requested_by_key = {}

    # 1. Tum girdileri veritabanina gitmeden dogrula.
    for item in reservations:
        if not isinstance(item, dict):
            raise ValueError("Rezervasyon bir nesne olmali.")

        if set(item.keys()) != required_fields:
            raise ValueError(
                "Rezervasyon alanlari gecersiz."
            )

        reservation_id = item["reservation_id"]
        employee_id = item["employee_id"]
        day = item["capacity_date"]
        hours = item["reserved_hours"]

        if (
            not isinstance(reservation_id, str)
            or not reservation_id.strip()
        ):
            raise ValueError("reservation_id gecersiz.")

        if (
            not isinstance(employee_id, str)
            or not employee_id.strip()
        ):
            raise ValueError("employee_id gecersiz.")

        _parse_iso_date(day, "capacity_date")

        if type(hours) is not int or hours <= 0:
            raise ValueError(
                "reserved_hours pozitif tam sayi olmali."
            )

        if reservation_id in seen_ids:
            raise ValueError(
                "Batch icinde duplicate reservation_id."
            )

        seen_ids.add(reservation_id)

        key = (employee_id, day)
        requested_by_key[key] = (
            requested_by_key.get(key, 0) + hours
        )

    # 2. Kontrol ve yazma tek transaction icinde.
    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            # Ayni ID daha once kullanilmis mi?
            for reservation_id in seen_ids:
                existing = connection.execute("""
                    SELECT 1
                    FROM daily_reservations
                    WHERE reservation_id = ?
                """, (reservation_id,)).fetchone()

                if existing is not None:
                    raise ValueError(
                        "Rezervasyon kimligi zaten mevcut."
                    )

            # 3. Her calisan/gun icin toplam talebi kontrol et.
            for (employee_id, day), requested in (
                requested_by_key.items()
            ):
                capacity = connection.execute("""
                    SELECT available_hours
                    FROM employee_daily_capacity
                    WHERE employee_id = ?
                      AND planning_period = ?
                      AND capacity_date = ?
                """, (
                    employee_id,
                    planning_period,
                    day,
                )).fetchone()

                if capacity is None:
                    raise ValueError(
                        "Gunluk kapasite kaydi bulunamadi: "
                        f"{employee_id}, {day}"
                    )

                reserved = connection.execute("""
                    SELECT COALESCE(
                        SUM(reserved_hours), 0
                    ) AS total_reserved
                    FROM daily_reservations
                    WHERE employee_id = ?
                      AND planning_period = ?
                      AND capacity_date = ?
                """, (
                    employee_id,
                    planning_period,
                    day,
                )).fetchone()["total_reserved"]

                remaining = (
                    capacity["available_hours"] - reserved
                )

                if requested > remaining:
                    raise ValueError(
                        "Yetersiz gunluk kapasite: "
                        f"{employee_id}, {day}. "
                        f"Kalan: {remaining}, "
                        f"istenen: {requested}."
                    )

            # 4. Tum kontroller gectiyse kayitlari ekle.
            for item in reservations:
                connection.execute("""
                    INSERT INTO daily_reservations (
                        reservation_id,
                        plan_id,
                        employee_id,
                        planning_period,
                        capacity_date,
                        reserved_hours
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    item["reservation_id"],
                    plan_id,
                    item["employee_id"],
                    planning_period,
                    item["capacity_date"],
                    item["reserved_hours"],
                ))

            connection.commit()

            return {
                "success": True,
                "plan_id": plan_id,
                "reservation_count": len(reservations),
                "total_reserved_hours": sum(
                    item["reserved_hours"]
                    for item in reservations
                ),
                "reservation_ids": [
                    item["reservation_id"]
                    for item in reservations
                ],
            }

        except Exception:
            connection.rollback()
            raise


if __name__ == "__main__":
    initialize_reservation_schema()
    print("Gunluk rezervasyon tablosu hazir.")


import argparse
import json
from contextlib import closing

from database import PLANNING_PERIOD, connect_db
from dated_capacity import check_dated_capacity

from dated_reservations import (
    initialize_reservation_schema,
    reserve_daily_hours,
)


RESERVATION_ID = "RES-DEMO-NET-001"
PLAN_ID = "PLAN-DEMO-NET-001"
EMPLOYEE_ID = "EMP-001"
DAY = "2026-11-16"
HOURS = 3


def show_capacity():
    result = check_dated_capacity(
        required_skill="backend",
        required_hours=14,
        start_date="2026-11-16",
        end_date="2026-11-17",
    )

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
    ))


def add_demo():
    with closing(connect_db()) as connection:
        existing = connection.execute("""
            SELECT 1
            FROM daily_reservations
            WHERE reservation_id = ?
        """, (RESERVATION_ID,)).fetchone()

    if existing:
        print("Demo rezervasyonu zaten mevcut.")
        print("Tekrar rezervasyon olusturulmadi.")
        return

    result = reserve_daily_hours(
        reservation_id=RESERVATION_ID,
        plan_id=PLAN_ID,
        employee_id=EMPLOYEE_ID,
        capacity_date=DAY,
        reserved_hours=HOURS,
    )

    print("Demo rezervasyonu olusturuldu.")
    print(json.dumps(result, indent=2))


def remove_demo():
    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            cursor = connection.execute("""
                DELETE FROM daily_reservations
                WHERE reservation_id = ?
                  AND plan_id = ?
                  AND employee_id = ?
                  AND planning_period = ?
                  AND capacity_date = ?
                  AND reserved_hours = ?
            """, (
                RESERVATION_ID,
                PLAN_ID,
                EMPLOYEE_ID,
                PLANNING_PERIOD,
                DAY,
                HOURS,
            ))

            deleted = cursor.rowcount
            connection.commit()

        except Exception:
            connection.rollback()
            raise

    if deleted:
        print("Demo rezervasyonu silindi.")
    else:
        print("Eslesen demo rezervasyonu bulunamadi.")
        print("Baska kayitlara dokunulmadi.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=["show", "add", "remove"],
    )

    args = parser.parse_args()

    # Gercek SQLite veritabaninda rezervasyon
    # tablosunun mevcut oldugundan emin ol.
    initialize_reservation_schema()

    if args.action == "add":
        add_demo()
    elif args.action == "remove":
        remove_demo()

    print("\n=== Guncel kapasite ===")
    show_capacity()


if __name__ == "__main__":
    main()

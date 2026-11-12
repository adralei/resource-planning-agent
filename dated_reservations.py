
"""Initialize and read daily employee reservation records."""

from contextlib import closing

from database import connect_db
from dated_capacity import initialize_daily_capacity_schema


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


if __name__ == "__main__":
    initialize_reservation_schema()
    print("Gunluk rezervasyon tablosu hazir.")

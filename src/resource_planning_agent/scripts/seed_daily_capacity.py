
"""Seed demo daily-capacity records and print a dated capacity check."""

import json
from contextlib import closing

from resource_planning_agent.storage.database import (
    PLANNING_PERIOD,
    connect_db,
)
from resource_planning_agent.planning.dated_capacity import (
    check_dated_capacity,
    initialize_daily_capacity_schema,
)


DEMO_CAPACITIES = [
    ("EMP-001", "2026-11-16", 4),
    ("EMP-001", "2026-11-17", 4),
    ("EMP-002", "2026-11-16", 2),
    ("EMP-002", "2026-11-17", 2),
]


def seed_daily_capacity():
    initialize_daily_capacity_schema()

    inserted = 0
    skipped = 0

    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            for employee_id, day, hours in DEMO_CAPACITIES:
                cursor = connection.execute(
                    """
                    INSERT INTO employee_daily_capacity (
                        employee_id,
                        planning_period,
                        capacity_date,
                        available_hours
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (
                        employee_id,
                        planning_period,
                        capacity_date
                    ) DO NOTHING
                    """,
                    (employee_id, PLANNING_PERIOD, day, hours),
                )

                if cursor.rowcount == 1:
                    inserted += 1
                else:
                    skipped += 1

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    print(f"Yeni kayit: {inserted}")
    print(f"Korunan mevcut kayit: {skipped}")


def main():
    seed_daily_capacity()

    result = check_dated_capacity(
        required_skill="backend",
        required_hours=14,
        start_date="2026-11-16",
        end_date="2026-11-17",
    )

    print("\n=== SQLite kapasite sonucu ===")
    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()

import sqlite3
from contextlib import closing
from pathlib import Path

from resource_proposal import OTHER_TEAM_EMPLOYEES


DB_PATH = Path(__file__).resolve().parent / "data" / "resource_planning.db"
PLANNING_PERIOD = "prototype_fixed_period"


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        DB_PATH,
        timeout=5.0,
        isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database():
    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS employee_capacity (
                    employee_id TEXT NOT NULL,
                    planning_period TEXT NOT NULL,
                    name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    skill TEXT NOT NULL,
                    available_hours INTEGER NOT NULL
                        CHECK (
                            typeof(available_hours) = 'integer'
                            AND available_hours >= 0
                        ),
                    PRIMARY KEY (employee_id, planning_period)
                )
            """)

            for employee in OTHER_TEAM_EMPLOYEES:
                connection.execute("""
                    INSERT INTO employee_capacity (
                        employee_id,
                        planning_period,
                        name,
                        team,
                        skill,
                        available_hours
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(employee_id, planning_period) DO NOTHING
                """, (
                    employee["employee_id"],
                    PLANNING_PERIOD,
                    employee["name"],
                    employee["team"],
                    employee["skill"],
                    employee["available_hours"],
                ))

            connection.commit()

        except Exception:
            connection.rollback()
            raise


def read_employee_capacities(planning_period):
    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT
                employee_id,
                planning_period,
                name,
                team,
                skill,
                available_hours
            FROM employee_capacity
            WHERE planning_period = ?
            ORDER BY employee_id
        """, (planning_period,)).fetchall()

    return [dict(row) for row in rows]


def read_plan_application(plan_id):
    with closing(connect_db()) as connection:
        table_exists = connection.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'applied_plans'
        """).fetchone()

        if table_exists is None:
            return None

        row = connection.execute("""
            SELECT plan_id, applied_at
            FROM applied_plans
            WHERE plan_id = ?
        """, (plan_id,)).fetchone()

    return dict(row) if row is not None else None


def main():
    initialize_database()

    employees = read_employee_capacities(PLANNING_PERIOD)

    print(f"Veritabanı: {DB_PATH}")
    print(f"Dönem: {PLANNING_PERIOD}")
    print(f"Kayıt sayısı: {len(employees)}")

    for employee in employees:
        print(
            f"- {employee['employee_id']} | "
            f"{employee['name']} | "
            f"{employee['team']} | "
            f"{employee['skill']} | "
            f"{employee['available_hours']} saat"
        )


if __name__ == "__main__":
    main()
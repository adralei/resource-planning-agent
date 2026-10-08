import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from database import connect_db, initialize_database, PLANNING_PERIOD
from plan_store import load_plan
from plan_validation import validate_plan_for_assignment


def apply_approved_plan(plan_id):
    plan = load_plan(plan_id)

    # Uygulanan planın içeriğini de saklayacağız.
    snapshot = json.dumps(
        plan,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS applied_plans (
                    plan_id TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    plan_snapshot TEXT NOT NULL
                )
            """)

            existing = connection.execute("""
                SELECT applied_at, plan_snapshot
                FROM applied_plans
                WHERE plan_id = ?
            """, (plan["plan_id"],)).fetchone()

            if existing is not None:
                if existing["plan_snapshot"] != snapshot:
                    raise ValueError(
                        "Bu plan kimliği daha önce farklı içerikle uygulanmış."
                    )

                connection.commit()
                return {
                    "status": "already_applied",
                    "applied_at": existing["applied_at"],
                }

            rows = connection.execute("""
                SELECT employee_id, name, team, skill, available_hours
                FROM employee_capacity
                WHERE planning_period = ?
            """, (PLANNING_PERIOD,)).fetchall()

            employees = [dict(row) for row in rows]

            validation = validate_plan_for_assignment(
                plan,
                employees,
                PLANNING_PERIOD,
            )

            if not validation["checks_passed"]:
                raise ValueError("\n".join(validation["issues"]))

            for allocation in plan["proposal"]["allocations"]:
                hours = allocation["proposed_hours"]

                cursor = connection.execute("""
                    UPDATE employee_capacity
                    SET available_hours = available_hours - ?
                    WHERE employee_id = ?
                      AND planning_period = ?
                      AND available_hours >= ?
                """, (
                    hours,
                    allocation["employee_id"],
                    PLANNING_PERIOD,
                    hours,
                ))

                if cursor.rowcount != 1:
                    raise ValueError(
                        "Kapasite güncellenemedi: "
                        f"{allocation['employee_id']}"
                    )

            applied_at = datetime.now(timezone.utc).isoformat()

            connection.execute("""
                INSERT INTO applied_plans (
                    plan_id, applied_at, plan_snapshot
                )
                VALUES (?, ?, ?)
            """, (plan["plan_id"], applied_at, snapshot))

            connection.commit()

            return {
                "status": "applied",
                "applied_at": applied_at,
            }

        except Exception:
            connection.rollback()
            raise


def main():
    initialize_database()
    plan_id = input("Uygulanacak onaylı plan kimliği: ").strip()

    try:
        result = apply_approved_plan(plan_id)
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"Plan uygulanamadı: {error}")
        return

    if result["status"] == "already_applied":
        print("Bu plan daha önce uygulanmış; kapasite tekrar düşülmedi.")
    else:
        print("Plan yerel demo veritabanına uygulandı.")
        print("Kapasite düşümleri ve uygulama kaydı birlikte kaydedildi.")

    print(f"Uygulama zamanı: {result['applied_at']}")


if __name__ == "__main__":
    main()
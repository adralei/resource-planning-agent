"""Tarih bazli kapasiteyi guvenli, salt-okunur sekilde sorgulama prototipi.

Bu modul mevcut sabit donemli check_capacity / apply_plan akislarini degistirmez.
Gunun bos saatleri ayrica kaydedilir; atama veya rezervasyon yapilmaz.
"""

import json
import re
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from database import (
    PLANNING_PERIOD,
    PRIMARY_TEAM,
    connect_db,
    initialize_database,
)

SUPPORTED_SKILLS = frozenset({"backend", "devops", "frontend"})
MAX_DAYS_PER_QUERY = 31
ISO_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def _parse_iso_date(value, field):
    if not isinstance(value, str) or not ISO_DATE_PATTERN.fullmatch(value):
        raise ValueError(f"{field} YYYY-MM-DD formatinda olmalidir.")

    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} gecerli bir takvim tarihi olmalidir.") from error

    if parsed.isoformat() != value:
        raise ValueError(f"{field} YYYY-MM-DD formatinda olmalidir.")

    return parsed


def initialize_daily_capacity_schema():
    """Gunluk tabloyu ekler; eski capacity kayitlarini ve planlari degistirmez."""
    initialize_database()
    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS employee_daily_capacity (
                    employee_id TEXT NOT NULL,
                    planning_period TEXT NOT NULL,
                    capacity_date TEXT NOT NULL
                        CHECK (capacity_date GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
                    available_hours INTEGER NOT NULL
                        CHECK (
                            typeof(available_hours) = 'integer'
                            AND available_hours BETWEEN 0 AND 24
                        ),
                    PRIMARY KEY (employee_id, planning_period, capacity_date),
                    FOREIGN KEY (employee_id, planning_period)
                        REFERENCES employee_capacity(employee_id, planning_period)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_capacity_period_date
                ON employee_daily_capacity (planning_period, capacity_date)
            """)
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def set_daily_capacity(employee_id, capacity_date, available_hours,
                       planning_period=PLANNING_PERIOD):
    """Acikca cagrildiginda tek bir calisanin gunluk bos saatini kaydeder.

    Mevcut bir satiri gunceller; uygulama katmaninin varsayilan davranisi degildir.
    Tablo once initialize_daily_capacity_schema ile olusturulmalidir.
    """
    if not isinstance(employee_id, str) or not employee_id.strip():
        raise ValueError("employee_id bos olamaz.")
    if not isinstance(planning_period, str) or not planning_period.strip():
        raise ValueError("planning_period bos olamaz.")
    _parse_iso_date(capacity_date, "capacity_date")

    if type(available_hours) is not int or not 0 <= available_hours <= 24:
        raise ValueError("available_hours 0 ile 24 arasinda tam sayi olmali.")

    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("""
                INSERT INTO employee_daily_capacity (
                    employee_id, planning_period, capacity_date, available_hours
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(employee_id, planning_period, capacity_date)
                DO UPDATE SET available_hours = excluded.available_hours
            """, (employee_id, planning_period, capacity_date, available_hours))
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def check_dated_capacity(required_skill, required_hours, start_date, end_date,
                         team=PRIMARY_TEAM, planning_period=PLANNING_PERIOD):
    """Tarih araligindaki teyitli bos saatleri toplar; verideki bosluklarda karar vermez.

    Eksik gunluk kayit varsa total_capacity, shortage ve is_sufficient = None.
    'known_available_hours' ise sadece bulunan satirlarin toplamini ifade eder.
    """
    if not isinstance(required_skill, str) or required_skill not in SUPPORTED_SKILLS:
        raise ValueError("Desteklenmeyen yetkinlik.")
    if type(required_hours) is not int or required_hours <= 0:
        raise ValueError("required_hours pozitif bir tam sayi olmali.")
    if not isinstance(team, str) or not team.strip():
        raise ValueError("team bos olamaz.")
    if not isinstance(planning_period, str) or not planning_period.strip():
        raise ValueError("planning_period bos olamaz.")

    start = _parse_iso_date(start_date, "start_date")
    end = _parse_iso_date(end_date, "end_date")
    if end < start:
        raise ValueError("end_date start_date'den once olamaz.")

    day_count = (end - start).days + 1
    if day_count > MAX_DAYS_PER_QUERY:
        raise ValueError(f"Bir sorgu en fazla {MAX_DAYS_PER_QUERY} gun icerebilir.")

    expected_dates = [
        (start + timedelta(days=offset)).isoformat()
        for offset in range(day_count)
    ]

    reserved_by_key = {}

    with closing(connect_db()) as connection:
        employees = [dict(row) for row in connection.execute("""
            SELECT employee_id, name
            FROM employee_capacity
            WHERE planning_period = ? AND team = ? AND skill = ?
            ORDER BY employee_id
        """, (planning_period, team, required_skill)).fetchall()]

        rows = connection.execute("""
            SELECT dc.employee_id, dc.capacity_date, dc.available_hours
            FROM employee_daily_capacity dc
            JOIN employee_capacity e
              ON e.employee_id = dc.employee_id
             AND e.planning_period = dc.planning_period
            WHERE dc.planning_period = ?
              AND e.team = ? AND e.skill = ?
              AND dc.capacity_date BETWEEN ? AND ?
        """, (planning_period, team, required_skill,
              start_date, end_date)).fetchall()

        # Eski test veritabanlarinda rezervasyon
        # tablosu henuz bulunmayabilir.
        reservation_table_exists = connection.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'daily_reservations'
        """).fetchone()

        if reservation_table_exists:
            reservation_rows = connection.execute("""
                SELECT
                    r.employee_id,
                    r.capacity_date,
                    SUM(r.reserved_hours) AS reserved_hours
                FROM daily_reservations r
                JOIN employee_capacity e
                  ON e.employee_id = r.employee_id
                 AND e.planning_period = r.planning_period
                WHERE r.planning_period = ?
                  AND e.team = ?
                  AND e.skill = ?
                  AND r.capacity_date BETWEEN ? AND ?
                GROUP BY r.employee_id, r.capacity_date
            """, (
                planning_period,
                team,
                required_skill,
                start_date,
                end_date,
            )).fetchall()

            reserved_by_key = {
                (row["employee_id"], row["capacity_date"]):
                    row["reserved_hours"]
                for row in reservation_rows
            }


    records = {
        (row["employee_id"], row["capacity_date"]): row["available_hours"]
        for row in rows
    }

    missing = []
    known_hours = 0

    for employee in employees:
        for day in expected_dates:
            key = (employee["employee_id"], day)
            hours = records.get(key)

            if hours is None:
                missing.append({
                    "employee_id": employee["employee_id"],
                    "date": day,
                })
                continue

            reserved = reserved_by_key.get(key, 0)

            # Veri tutarsizligi varsa kesin sonuc uretme.
            if reserved > hours:
                raise ValueError(
                    f"Rezervasyon kapasiteyi asiyor: {key}"
                )

            remaining = hours - reserved
            known_hours += remaining


    complete = not missing
    total = known_hours if complete else None
    shortage = max(0, required_hours - total) if complete else None

    return {
        "planning_period": planning_period,
        "team": team,
        "required_skill": required_skill,
        "required_hours": required_hours,
        "start_date": start_date,
        "end_date": end_date,
        "candidates": [employee["name"] for employee in employees],
        "known_available_hours": known_hours,
        "data_complete": complete,
        "missing_availability": missing,
        "total_capacity": total,
        "shortage": shortage,
        "is_sufficient": (shortage == 0) if complete else None,
        "status": "calculated" if complete else "missing_daily_data",
    }


def main():
    # Bu ornek, kullanicinin gercek data/resource_planning.db dosyasina DOKUNMAZ.
    with tempfile.TemporaryDirectory() as folder:
        with patch("database.DB_PATH", Path(folder) / "dated_demo.db"):
            initialize_daily_capacity_schema()
            for employee_id, day, hours in (
                ("EMP-001", "2026-11-16", 4),
                ("EMP-001", "2026-11-17", 4),
                ("EMP-002", "2026-11-16", 2),
                ("EMP-002", "2026-11-17", 2),
            ):
                set_daily_capacity(employee_id, day, hours)

            for label, start, end in (
                ("Eksiksiz gunluk veri", "2026-11-16", "2026-11-17"),
                ("Eksik gunluk veri", "2026-11-16", "2026-11-18"),
            ):
                result = check_dated_capacity("backend", 14, start, end)
                print(f"\n=== {label} ===")
                print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from resource_planning_agent.storage.database import connect_db
from resource_planning_agent.planning.plan_fingerprint import (
    calculate_plan_fingerprint,
    verify_plan_fingerprint,
)


HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def initialize_approval_registry():
    """
    Plan JSON dosyasindan ayri fingerprint tablosu.
    Mevcut kayitlari degistirmez.
    """

    with closing(connect_db()) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS approval_fingerprints (
                plan_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            )
        """)


def record_approval_fingerprint(plan):
    """
    Onaylanmis planin fingerprint'ini bir kez kaydeder.
    Var olan kayitlarin uzerine yazmaz.

    Not: Bu fonksiyon tek basina kimlik dogrulama
    veya onay yetkilendirmesi yapmaz.
    """

    if not isinstance(plan, dict):
        raise ValueError("Plan nesnesi gecersiz.")

    plan_id = plan.get("plan_id")

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    if plan.get("status") != "approved":
        raise ValueError("Yalnizca onayli plan kaydedilebilir.")

    fingerprint = plan.get("approval_fingerprint")

    if not isinstance(fingerprint, str) or not HASH_PATTERN.fullmatch(
        fingerprint
    ):
        raise ValueError("Onay fingerprint'i gecersiz.")

    if not verify_plan_fingerprint(plan, fingerprint):
        raise ValueError("Plan fingerprint eslesmiyor.")

    recorded_at = datetime.now(timezone.utc).isoformat()

    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            connection.execute("""
                INSERT INTO approval_fingerprints (
                    plan_id,
                    fingerprint,
                    recorded_at
                )
                VALUES (?, ?, ?)
            """, (
                plan_id,
                fingerprint,
                recorded_at,
            ))

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    return {
        "plan_id": plan_id,
        "fingerprint": fingerprint,
        "recorded_at": recorded_at,
    }


def read_approval_fingerprint(plan_id):
    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    with closing(connect_db()) as connection:
        row = connection.execute("""
            SELECT plan_id, fingerprint, recorded_at
            FROM approval_fingerprints
            WHERE plan_id = ?
        """, (plan_id,)).fetchone()

    return dict(row) if row is not None else None


def verify_registered_approval(plan):
    """
    Kayitli fingerprint ile plan icerigini karsilastirir.
    Kayit bulunamazsa fail-closed davranir.
    """

    if not isinstance(plan, dict):
        return False

    plan_id = plan.get("plan_id")

    if not isinstance(plan_id, str) or not plan_id.strip():
        return False

    if plan.get("status") != "approved":
        return False

    registered = read_approval_fingerprint(plan_id)

    if registered is None:
        return False

    try:
        actual = calculate_plan_fingerprint(plan)
    except ValueError:
        return False

    return (
        plan.get("approval_fingerprint") == registered["fingerprint"]
        and actual == registered["fingerprint"]
    )

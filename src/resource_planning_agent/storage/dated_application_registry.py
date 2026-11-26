
import re
from contextlib import closing
from datetime import datetime, timezone

from resource_planning_agent.storage.database import (
    connect_db,
)


def initialize_dated_application_registry():
    """
    Basarili tarihli plan uygulamalarinin kayit tablosu.

    plan_id PRIMARY KEY:
    Ayni planin ikinci uygulama kaydini engeller.
    """

    with closing(connect_db()) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS
                dated_plan_applications (
                    plan_id TEXT PRIMARY KEY,
                    approval_fingerprint TEXT NOT NULL,
                    reservation_count INTEGER NOT NULL
                        CHECK (reservation_count > 0),
                    applied_at TEXT NOT NULL
                )
        """)

        connection.commit()


def read_dated_application_record(plan_id):
    """
    Planin uygulama kaydini okur.

    Kayit yoksa None doner.
    Veritabanina yazmaz.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    with closing(connect_db()) as connection:
        row = connection.execute("""
            SELECT
                plan_id,
                approval_fingerprint,
                reservation_count,
                applied_at
            FROM dated_plan_applications
            WHERE plan_id = ?
        """, (plan_id,)).fetchone()

    if row is None:
        return None

    return dict(row)


def insert_dated_application_record(
    connection,
    plan_id,
    approval_fingerprint,
    reservation_count,
):
    """
    Uygulama kaydini mevcut SQLite transaction'ina ekler.

    ONEMLI:
    - Yeni connection acmaz.
    - BEGIN veya COMMIT yapmaz.
    - Rollback yapmaz.
    - Transaction yonetimi cagirana aittir.

    Boylece ileride rezervasyonlarla ayni transaction
    icinde kullanilabilir.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    if (
        not isinstance(approval_fingerprint, str)
        or re.fullmatch(
            r"[0-9a-f]{64}",
            approval_fingerprint,
        ) is None
    ):
        raise ValueError(
            "Gecerli SHA-256 approval fingerprint gerekli."
        )

    if (
        type(reservation_count) is not int
        or reservation_count <= 0
    ):
        raise ValueError(
            "Pozitif reservation_count gerekli."
        )

    if (
        connection is None
        or not connection.in_transaction
    ):
        raise ValueError(
            "Aktif SQLite transaction gerekli."
        )

    applied_at = datetime.now(
        timezone.utc
    ).isoformat()

    connection.execute("""
        INSERT INTO dated_plan_applications (
            plan_id,
            approval_fingerprint,
            reservation_count,
            applied_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        plan_id,
        approval_fingerprint,
        reservation_count,
        applied_at,
    ))

    return {
        "plan_id": plan_id,
        "approval_fingerprint": approval_fingerprint,
        "reservation_count": reservation_count,
        "applied_at": applied_at,
    }

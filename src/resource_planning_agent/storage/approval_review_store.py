
import json
from contextlib import closing

from resource_planning_agent.storage.database import (
    connect_db,
)


REQUIRED_FIELDS = {
    "case_id",
    "plan_id",
    "created_at",
    "case_status",
    "consistency_status",
    "recommended_action",
    "reason",
    "required_evidence",
    "review_steps",
    "manual_review_required",
    "automatic_recovery_allowed",
    "can_proceed_to_preflight",
    "approval_granted",
    "registry_modified",
    "reservations_created",
}

REVIEWABLE_STATUSES = {
    "missing_registry",
    "fingerprint_mismatch",
    "missing_fingerprint",
    "invalid_plan",
}


def initialize_review_case_store():
    """
    Review case tablosunu olusturur veya eski semayi
    yeni lifecycle semasina tasir.

    Mevcut vakalar korunur.
    Migration tek transaction icinde gerceklesir.
    """

    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS approval_review_cases (
                    case_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    case_status TEXT NOT NULL
                        CHECK (
                            case_status IN (
                                'awaiting_manual_review',
                                'reviewed'
                            )
                        ),
                    consistency_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    case_data TEXT NOT NULL
                )
            """)

            row = connection.execute("""
                SELECT sql
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'approval_review_cases'
            """).fetchone()

            if row is None:
                raise RuntimeError(
                    "Review case tablosu bulunamadi."
                )

            current_schema = row["sql"]

            # Eski sema yalnizca awaiting_manual_review
            # durumunu kabul ediyordu.
            needs_migration = (
                "'reviewed'" not in current_schema
            )

            if needs_migration:
                connection.execute("""
                    CREATE TABLE approval_review_cases_new (
                        case_id TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL,
                        case_status TEXT NOT NULL
                            CHECK (
                                case_status IN (
                                    'awaiting_manual_review',
                                    'reviewed'
                                )
                            ),
                        consistency_status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        case_data TEXT NOT NULL
                    )
                """)

                connection.execute("""
                    INSERT INTO approval_review_cases_new (
                        case_id,
                        plan_id,
                        case_status,
                        consistency_status,
                        created_at,
                        case_data
                    )
                    SELECT
                        case_id,
                        plan_id,
                        case_status,
                        consistency_status,
                        created_at,
                        case_data
                    FROM approval_review_cases
                """)

                connection.execute("""
                    DROP TABLE approval_review_cases
                """)

                connection.execute("""
                    ALTER TABLE approval_review_cases_new
                    RENAME TO approval_review_cases
                """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_review_cases_plan_id
                ON approval_review_cases (plan_id)
            """)

            connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    idx_one_open_review_per_plan
                ON approval_review_cases (plan_id)
                WHERE case_status = 'awaiting_manual_review'
            """)

            connection.commit()

        except Exception:
            connection.rollback()
            raise


def save_approval_review_case(review_case):
    """
    Hazirlanmis inceleme paketini kaydeder.

    Bu fonksiyon:
    - Yeni onay vermez.
    - Plan durumunu degistirmez.
    - Approval Registry kaydina dokunmaz.
    - Rezervasyon olusturmaz.
    """

    if not isinstance(review_case, dict):
        raise ValueError("Review case nesnesi gecersiz.")

    if not REQUIRED_FIELDS.issubset(review_case):
        raise ValueError("Review case alanlari eksik.")

    case_id = review_case["case_id"]
    plan_id = review_case["plan_id"]

    if (
        not isinstance(case_id, str)
        or not case_id.strip()
        or not isinstance(plan_id, str)
        or not plan_id.strip()
    ):
        raise ValueError("Case veya plan kimligi gecersiz.")

    if (
        not isinstance(review_case["created_at"], str)
        or not review_case["created_at"].strip()
    ):
        raise ValueError("Case olusturma zamani gecersiz.")

    if review_case["case_status"] != "awaiting_manual_review":
        raise ValueError("Review case durumu gecersiz.")

    if review_case["consistency_status"] not in REVIEWABLE_STATUSES:
        raise ValueError("Consistency durumu gecersiz.")

    safety_fields = {
        "manual_review_required": True,
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": False,
        "approval_granted": False,
        "registry_modified": False,
        "reservations_created": False,
    }

    for field, expected in safety_fields.items():
        if review_case[field] is not expected:
            raise ValueError(
                f"Guvenlik alani gecersiz: {field}"
            )

    for field in ("required_evidence", "review_steps"):
        value = review_case[field]

        if (
            not isinstance(value, list)
            or not value
            or not all(
                isinstance(item, str) and item.strip()
                for item in value
            )
        ):
            raise ValueError(
                f"Review case listesi gecersiz: {field}"
            )

    for field in ("recommended_action", "reason"):
        value = review_case[field]

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Review case metni gecersiz: {field}"
            )

    try:
        case_json = json.dumps(
            review_case,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Review case JSON formatina donusturulemedi."
        ) from error

    with closing(connect_db()) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            connection.execute("""
                INSERT INTO approval_review_cases (
                    case_id,
                    plan_id,
                    case_status,
                    consistency_status,
                    created_at,
                    case_data
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                case_id,
                plan_id,
                review_case["case_status"],
                review_case["consistency_status"],
                review_case["created_at"],
                case_json,
            ))

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    return {
        "saved": True,
        "case_id": case_id,
        "plan_id": plan_id,
        "case_status": review_case["case_status"],
    }


def load_approval_review_case(case_id):
    """
    Kayitli inceleme paketini okur.
    Kayit bulunamazsa None doner.
    """

    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("Gecerli case_id gerekli.")

    with closing(connect_db()) as connection:
        row = connection.execute("""
            SELECT case_data
            FROM approval_review_cases
            WHERE case_id = ?
        """, (case_id,)).fetchone()

    if row is None:
        return None

    return json.loads(row["case_data"])


def get_open_review_case_for_plan(plan_id):
    """
    Bir planin mevcut acik inceleme vakasini getirir.

    Kayit bulunamazsa None doner.
    Veritabanina yazmaz.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    with closing(connect_db()) as connection:
        row = connection.execute("""
            SELECT case_data
            FROM approval_review_cases
            WHERE plan_id = ?
              AND case_status = 'awaiting_manual_review'
        """, (plan_id,)).fetchone()

    if row is None:
        return None

    return json.loads(row["case_data"])


from collections import Counter

from resource_planning_agent.storage.database import PLANNING_PERIOD


REQUIRED_FIELDS = {
    "reservation_id",
    "employee_id",
    "capacity_date",
    "reserved_hours",
}


def validate_approved_dated_plan(plan, reservations):
    """
    Gunluk rezervasyonlarin onayli planla
    eslesip eslesmedigini kontrol eder.

    Bu fonksiyon veritabanina yazmaz.
    """

    if plan.get("status") != "approved":
        raise ValueError("Plan henuz onaylanmamis.")

    if plan.get("planning_period") != PLANNING_PERIOD:
        raise ValueError("Planlama donemi uyusmuyor.")

    proposal = plan.get("proposal", {})
    allocations = proposal.get("allocations", [])
    approved_items = proposal.get("dated_reservations")

    if not isinstance(allocations, list) or not allocations:
        raise ValueError("Plan kaynak dagilimi eksik.")

    if not isinstance(approved_items, list) or not approved_items:
        raise ValueError(
            "Planda onaylanmis gunluk rezervasyonlar yok."
        )

    if not isinstance(reservations, list) or not reservations:
        raise ValueError("Rezervasyon talebi bos olamaz.")

    # Proje ve ilgili tum ekiplerin onaylari gerekli.
    try:
        expected_scopes = {
            ("project_manager", plan["project_id"]),
        }

        allowed_employees = set()

        for allocation in allocations:
            expected_scopes.add((
                "team_manager",
                allocation["team"],
            ))
            allowed_employees.add(
                allocation["employee_id"]
            )

        approvals = plan["required_approvals"]

        actual_scopes = [
            (item["role"], item["scope"])
            for item in approvals
        ]

        all_approved = all(
            item["status"] == "approved"
            for item in approvals
        )

    except (KeyError, TypeError):
        raise ValueError(
            "Planin onay bilgileri gecersiz."
        ) from None

    if (
        not all_approved
        or len(actual_scopes) != len(expected_scopes)
        or set(actual_scopes) != expected_scopes
    ):
        raise ValueError(
            "Gerekli proje ve ekip onaylari eksik veya hatali."
        )

    def normalize(items):
        normalized = []
        seen_ids = set()

        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Rezervasyon nesnesi gecersiz.")

            if set(item) != REQUIRED_FIELDS:
                raise ValueError("Rezervasyon alanlari gecersiz.")

            reservation_id = item["reservation_id"]
            employee_id = item["employee_id"]
            day = item["capacity_date"]
            hours = item["reserved_hours"]

            if (
                not isinstance(reservation_id, str)
                or not reservation_id.strip()
                or not isinstance(employee_id, str)
                or not employee_id.strip()
                or not isinstance(day, str)
                or type(hours) is not int
                or hours <= 0
            ):
                raise ValueError("Rezervasyon degerleri gecersiz.")

            if reservation_id in seen_ids:
                raise ValueError(
                    "Tekrarlanan rezervasyon kimligi."
                )

            if employee_id not in allowed_employees:
                raise ValueError(
                    "Onay kapsaminda olmayan calisan."
                )

            seen_ids.add(reservation_id)

            normalized.append((
                reservation_id,
                employee_id,
                day,
                hours,
            ))

        return Counter(normalized)

    if normalize(approved_items) != normalize(reservations):
        raise ValueError(
            "Rezervasyon talebi onayli planla eslesmiyor."
        )

    return {
        "checks_passed": True,
        "plan_id": plan["plan_id"],
        "reservation_count": len(reservations),
    }

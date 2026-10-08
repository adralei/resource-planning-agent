import json


# Sentetik örnek veriler.
# Hepsi mevcut prototiple aynı sabit planlama dönemine aittir.
OTHER_TEAM_EMPLOYEES = [
    {
        "employee_id": "EMP-004",
        "name": "Deniz",
        "team": "Platform",
        "skill": "backend",
        "available_hours": 6,
    },
    {
        "employee_id": "EMP-005",
        "name": "Ece",
        "team": "Integrations",
        "skill": "backend",
        "available_hours": 2,
    },
    {
        "employee_id": "EMP-006",
        "name": "Fırat",
        "team": "Infrastructure",
        "skill": "devops",
        "available_hours": 8,
    },
    {
        "employee_id": "EMP-007",
        "name": "Gökçe",
        "team": "Payments",
        "skill": "backend",
        "available_hours": 0,
    },
]


def propose_resources(
    employees,
    required_skill,
    shortage,
    excluded_names=None,
):
    if type(shortage) is not int or shortage <= 0:
        raise ValueError("Kapasite açığı pozitif bir tam sayı olmalı.")

    if required_skill not in {"backend", "devops", "frontend"}:
        raise ValueError("Desteklenmeyen yetkinlik.")

    excluded_names = set(excluded_names or [])

    candidates = [
        employee
        for employee in employees
        if employee["skill"] == required_skill
        and employee["available_hours"] > 0
        and employee["name"] not in excluded_names
    ]

    # Eşit kapasitede kimliğe göre sıralayarak sonucu tutarlı tut.
    candidates.sort(
        key=lambda employee: (
            -employee["available_hours"],
            employee["employee_id"],
        )
    )

    remaining = shortage
    allocations = []

    for employee in candidates:
        if remaining == 0:
            break

        proposed_hours = min(
            employee["available_hours"],
            remaining,
        )

        allocations.append({
            "employee_id": employee["employee_id"],
            "name": employee["name"],
            "team": employee["team"],
            "available_hours": employee["available_hours"],
            "proposed_hours": proposed_hours,
        })

        remaining -= proposed_hours

    return {
        "status": "proposal_only",
        "required_skill": required_skill,
        "requested_shortage": shortage,
        "covered_hours": shortage - remaining,
        "remaining_shortage": remaining,
        "is_fully_covered": remaining == 0,
        "allocations": allocations,
    }


def main():
    result = propose_resources(
        employees=OTHER_TEAM_EMPLOYEES,
        required_skill="backend",
        shortage=4,
        excluded_names=["Ada", "Bora"],
    )

    print("KAYNAK ÖNERİSİ — ATAMA YAPILMADI")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
def check_capacity(employees, required_skill, required_hours):
    if required_hours <= 0:
        raise ValueError("İstenen saat sıfırdan büyük olmalıdır.")

    candidates = [
        employee
        for employee in employees
        if employee["skill"] == required_skill
    ]

    total_capacity = sum(
        employee["available_hours"]
        for employee in candidates
    )

    shortage = max(0, required_hours - total_capacity)

    return {
        "required_skill": required_skill,
        "required_hours": required_hours,
        "total_capacity": total_capacity,
        "shortage": shortage,
        "is_sufficient": shortage == 0,
        "candidates": [employee["name"] for employee in candidates],
    }


employees = [
    {"name": "Ada", "skill": "backend", "available_hours": 16},
    {"name": "Bora", "skill": "backend", "available_hours": 12},
    {"name": "Cem", "skill": "devops", "available_hours": 8},
]

if __name__ == "__main__":
    scenarios = [
        {"skill": "backend", "hours": 32},
        {"skill": "devops", "hours": 8},
        {"skill": "frontend", "hours": 10},
    ]

    for scenario in scenarios:
        result = check_capacity(
            employees=employees,
            required_skill=scenario["skill"],
            required_hours=scenario["hours"],
        )

        if not result["is_sufficient"]:
            print(
                f"Alternatif gerekiyor: "
                f"{result['shortage']} saat açık var."
            )

        print(result)
        print()
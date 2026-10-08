from copy import deepcopy

from plan_store import load_plan
from plan_validation import validate_plan_for_assignment
from resource_proposal import OTHER_TEAM_EMPLOYEES


def simulate_assignment(plan, employees, planning_period):
    # Girdi nesnelerini değiştirmeden bağımsız kopyalar üzerinde çalış.
    next_plan = deepcopy(plan)
    next_employees = deepcopy(employees)

    validation = validate_plan_for_assignment(
        next_plan,
        next_employees,
        planning_period,
    )

    if not validation["checks_passed"]:
        return {
            "ok": False,
            "issues": validation["issues"],
            "plan": next_plan,
            "employees": next_employees,
        }

    employees_by_id = {
        employee["employee_id"]: employee
        for employee in next_employees
    }

    # Bütün kontroller geçtikten sonra kapasite düşür.
    for allocation in next_plan["proposal"]["allocations"]:
        employee = employees_by_id[allocation["employee_id"]]
        employee["available_hours"] -= allocation["proposed_hours"]

    next_plan["status"] = "simulated_applied"

    return {
        "ok": True,
        "issues": [],
        "plan": next_plan,
        "employees": next_employees,
    }


def show_capacities(employees):
    for employee in employees:
        if employee["employee_id"] in {"EMP-004", "EMP-005"}:
            print(
                f"- {employee['name']}: "
                f"{employee['available_hours']} saat boş kapasite"
            )


def main():
    plan_id = input("Plan kimliği: ").strip()
    plan = load_plan(plan_id)
    period = "prototype_fixed_period"

    print("\nSENARYO 1 — Uygun planın simülasyonu")
    result = simulate_assignment(plan, OTHER_TEAM_EMPLOYEES, period)

    print(f"Başarılı: {result['ok']}")
    print(f"Simülasyondaki plan durumu: {result['plan']['status']}")
    show_capacities(result["employees"])

    print("\nSENARYO 2 — Aynı sonucu tekrar uygulama")
    repeated = simulate_assignment(
        result["plan"],
        result["employees"],
        period,
    )

    print(f"Başarılı: {repeated['ok']}")
    for issue in repeated["issues"]:
        print(f"- {issue}")
    show_capacities(repeated["employees"])

    print("\nSENARYO 3 — Deniz'in kapasitesi yetersiz")
    changed_employees = deepcopy(OTHER_TEAM_EMPLOYEES)

    for employee in changed_employees:
        if employee["employee_id"] == "EMP-004":
            employee["available_hours"] = 3

    failed = simulate_assignment(plan, changed_employees, period)

    print(f"Başarılı: {failed['ok']}")
    for issue in failed["issues"]:
        print(f"- {issue}")
    show_capacities(failed["employees"])

    print("\nAsıl örnek kayıtlar:")
    show_capacities(OTHER_TEAM_EMPLOYEES)
    print("Plan dosyası değiştirilmedi; sonuçlar yalnızca bellekte.")


if __name__ == "__main__":
    main()
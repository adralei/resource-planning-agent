from copy import deepcopy

from plan_store import load_plan
from resource_proposal import OTHER_TEAM_EMPLOYEES


def validate_plan_for_assignment(plan, employees, planning_period):
    issues = []

    if plan["status"] != "approved":
        issues.append("Plan onaylanmış durumda değil.")

    approvals = plan["required_approvals"]

    if not approvals or any(
        approval["status"] != "approved"
        for approval in approvals
    ):
        issues.append("Gerekli onayların tamamı alınmamış.")

    if plan["planning_period"] != planning_period:
        issues.append("Plan ile çalışan kayıtlarının dönemi eşleşmiyor.")

    employees_by_id = {}

    for employee in employees:
        employee_id = employee["employee_id"]

        if employee_id in employees_by_id:
            issues.append(f"Çalışan kaydında tekrarlanan kimlik: {employee_id}")

        employees_by_id[employee_id] = employee

    allocations = plan["proposal"]["allocations"]
    seen_ids = set()

    if not allocations:
        issues.append("Planda atanacak kaynak bulunmuyor.")

    for allocation in allocations:
        employee_id = allocation["employee_id"]

        if employee_id in seen_ids:
            issues.append(f"Planda çalışan birden fazla kez geçiyor: {employee_id}")
            continue

        seen_ids.add(employee_id)
        employee = employees_by_id.get(employee_id)

        if employee is None:
            issues.append(f"Çalışan güncel kayıtlarda bulunamadı: {employee_id}")
            continue

        hours = allocation["proposed_hours"]

        if type(hours) is not int or hours <= 0:
            issues.append(f"Önerilen saat geçersiz: {employee_id}")
            continue

        if employee["skill"] != plan["proposal"]["required_skill"]:
            issues.append(f"Çalışanın yetkinliği uygun değil: {employee_id}")

        if employee["team"] != allocation["team"]:
            issues.append(
                f"{employee['name']} için ekip değişmiş; "
                "onay kapsamı yeniden değerlendirilmeli."
            )

        available = employee["available_hours"]

        if type(available) is not int or available < 0:
            issues.append(f"Güncel kapasite kaydı geçersiz: {employee_id}")
        elif hours > available:
            issues.append(
                f"{employee['name']}: önerilen {hours} saat, "
                f"güncel boş kapasite {available} saat."
            )

    return {
        "checks_passed": not issues,
        "issues": issues,
    }


def show_result(label, result):
    print(f"\n{label}")

    if result["checks_passed"]:
        print("Bu kontroldeki koşullar sağlandı. Henüz atama yapılmadı.")
    else:
        print("Atama öncesi kontrol başarısız:")
        for issue in result["issues"]:
            print(f"- {issue}")


def main():
    plan_id = input("Plan kimliği: ").strip()
    plan = load_plan(plan_id)

    # Bu örnekte güncel kayıt kaynağını sentetik verilerle temsil ediyoruz.
    current_employees = deepcopy(OTHER_TEAM_EMPLOYEES)

    result = validate_plan_for_assignment(
        plan,
        current_employees,
        planning_period="prototype_fixed_period",
    )
    show_result("SENARYO 1 — Kapasiteler değişmedi", result)

    changed_employees = deepcopy(current_employees)

    for employee in changed_employees:
        if employee["employee_id"] == "EMP-004":
            employee["available_hours"] = 3

    result = validate_plan_for_assignment(
        plan,
        changed_employees,
        planning_period="prototype_fixed_period",
    )
    show_result("SENARYO 2 — Deniz'in kapasitesi 3 saate düştü", result)


if __name__ == "__main__":
    main()
import json

from plan_store import load_plan
from database import read_plan_application

def main():
    plan_id = input("Plan kimliği: ").strip()

    try:
        plan = load_plan(plan_id)
    except FileNotFoundError:
        print("Bu kimlikle kayıtlı plan bulunamadı.")
        return
    except (ValueError, json.JSONDecodeError):
        print("Plan kimliği veya kayıtlı plan dosyası geçersiz.")
        return

    proposal = plan["proposal"]

    print(f"\nPlan: {plan['plan_id']}")
    print(f"Proje: {plan['project_id']}")
    print(f"Onay süreci durumu: {plan['status']}")

    application = read_plan_application(plan["plan_id"])

    if application is None:
        print("Uygulama durumu: Uygulama kaydı bulunamadı.")
    else:
        print("Uygulama durumu: applied")
        print(f"Uygulama zamanı: {application['applied_at']}")
    print(f"Kapsama durumu: {plan['coverage_status']}")

    print("\nÖnerilen kaynaklar:")
    for allocation in proposal["allocations"]:
        print(
            f"- {allocation['name']} ({allocation['team']}): "
            f"{allocation['proposed_hours']} saat"
        )

    print(f"\nKalan açık: {proposal['remaining_shortage']} saat")

    print("\nGerekli onaylar:")
    for approval in plan["required_approvals"]:
        print(
            f"- {approval['role']} / {approval['scope']}: "
            f"{approval['status']}"
        )


if __name__ == "__main__":
    main()
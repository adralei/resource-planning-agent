from datetime import datetime, timezone

from plan_store import load_plan, update_plan


def submit_for_approval(plan_id):
    plan = load_plan(plan_id)

    if plan["status"] != "draft":
        raise ValueError(
            "Yalnızca draft durumundaki plan onay sürecine alınabilir. "
            f"Mevcut durum: {plan['status']}"
        )

    approvals = plan["required_approvals"]

    if not approvals:
        raise ValueError("Planın gerekli onayları tanımlanmamış.")

    if any(item["status"] != "not_requested" for item in approvals):
        raise ValueError("Taslağın onay kayıtları beklenen durumda değil.")

    if not plan["proposal"]["allocations"]:
        raise ValueError("Önerilen kaynak bulunmuyor.")

    submitted_at = datetime.now(timezone.utc).isoformat()

    plan["status"] = "pending_approval"
    plan["submitted_at"] = submitted_at

    for approval in approvals:
        approval["status"] = "pending"

    plan.setdefault("history", []).append({
        "event": "submitted_for_approval",
        "from_status": "draft",
        "to_status": "pending_approval",
        "timestamp": submitted_at,
        "origin": "local_demo_cli",
    })

    update_plan(plan)
    return plan


def main():
    plan_id = input("Onay sürecine alınacak plan kimliği: ").strip()

    try:
        plan = submit_for_approval(plan_id)
    except (ValueError, OSError) as error:
        print(f"İşlem tamamlanamadı: {error}")
        return

    print(f"\nPlan: {plan['plan_id']}")
    print(f"Durum: {plan['status']}")
    print(f"Kapsama durumu: {plan['coverage_status']}")
    print(
        "Kalan açık: "
        f"{plan['proposal']['remaining_shortage']} saat"
    )

    print("\nBekleyen onaylar:")
    for approval in plan["required_approvals"]:
        print(f"- {approval['role']} / {approval['scope']}")

    print("\nYerel onay kaydı güncellendi.")
    print("Bildirim gönderilmedi; atama veya rezervasyon yapılmadı.")


if __name__ == "__main__":
    main()
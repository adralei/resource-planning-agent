from datetime import datetime, timezone

from resource_planning_agent.storage.plan_store import load_plan, update_plan

from resource_planning_agent.planning.plan_fingerprint import (
    calculate_plan_fingerprint,
)


from resource_planning_agent.storage.approval_registry import (
    initialize_approval_registry,
    record_approval_fingerprint,
)



# Demo kullanıcıları: gerçek kimlik doğrulama yerine geçmez.
DEMO_USERS = {
    "manager_project": {
        "role": "project_manager",
        "scope": "DEMO-PROJECT-001",
    },
    "manager_platform": {
        "role": "team_manager",
        "scope": "Platform",
    },
    "manager_integrations": {
        "role": "team_manager",
        "scope": "Integrations",
    },
        "manager_project_002": {
        "role": "project_manager",
        "scope": "DEMO-PROJECT-002",
    },
    "manager_infrastructure": {
        "role": "team_manager",
        "scope": "Infrastructure",
    },
}


def approve_plan(plan_id, actor_id, approval_role, approval_scope):
    actor = DEMO_USERS.get(actor_id)

    if actor is None:
        raise PermissionError("Tanınmayan demo kullanıcı.")

    # Rol tek başına yeterli değil; ilgili proje veya ekip de eşleşmeli.
    if (
        actor["role"] != approval_role
        or actor["scope"] != approval_scope
    ):
        raise PermissionError("Bu kullanıcının bu onayı verme yetkisi yok.")

    plan = load_plan(plan_id)

    if plan["status"] != "pending_approval":
        raise ValueError(
            "Plan onay bekleyen durumda değil. "
            f"Mevcut durum: {plan['status']}"
        )

    matches = [
        approval
        for approval in plan["required_approvals"]
        if approval["role"] == approval_role
        and approval["scope"] == approval_scope
    ]

    if len(matches) != 1:
        raise ValueError("Planda tekil bir onay kaydı bulunamadı.")

    approval = matches[0]

    if approval["status"] != "pending":
        raise ValueError("Bu onay kaydı zaten işlenmiş veya beklemede değil.")

    now = datetime.now(timezone.utc).isoformat()

    approval["status"] = "approved"
    approval["approved_by"] = actor_id
    approval["approved_at"] = now

    all_approved = all(
        item["status"] == "approved"
        for item in plan["required_approvals"]
    )

    if all_approved:
        plan["status"] = "approved"

        proposal = plan.get("proposal", {})

        # Yalnizca tarihli rezervasyon planlarina
        # fingerprint uygula.
        if "dated_reservations" in proposal:

            # Onceden fingerprint bulunmasi,
            # onay surecinde beklenmeyen bir durumdur.
            if "approval_fingerprint" in plan:
                raise ValueError(
                    "Plan icin zaten fingerprint bulunuyor."
                )

            plan["approval_fingerprint"] = (
                calculate_plan_fingerprint(plan)
            )

    plan.setdefault("history", []).append({
        "event": "approval_recorded",
        "actor_id": actor_id,
        "role": approval_role,
        "scope": approval_scope,
        "timestamp": now,
        "plan_status_after": plan["status"],
        "origin": "local_demo_cli",
    })

    
    # Guncellenen onay durumunu JSON dosyasina kaydet.
    update_plan(plan)

    # Tum onaylar tamamlandiysa ve plan
    # tarihli rezervasyonlar iceriyorsa
    # fingerprint'i bagimsiz SQLite kaydina aktar.
    if all_approved and "dated_reservations" in plan.get(
        "proposal", {}
    ):
        initialize_approval_registry()
        record_approval_fingerprint(plan)

    return plan



def main():
    print("DEMO ONAY — gerçek kullanıcı girişi değildir.")

    plan_id = input("Plan kimliği: ").strip()
    actor_id = input("Demo kullanıcı kimliği: ").strip()
    role = input("Onay rolü: ").strip()
    scope = input("Onay kapsamı: ").strip()

    try:
        plan = approve_plan(plan_id, actor_id, role, scope)
    except (ValueError, OSError) as error:
        print(f"İşlem reddedildi veya tamamlanamadı: {error}")
        return

    print(f"\nPlan durumu: {plan['status']}")

    for approval in plan["required_approvals"]:
        print(
            f"- {approval['role']} / {approval['scope']}: "
            f"{approval['status']}"
        )

    print(f"\nKalan açık: {plan['proposal']['remaining_shortage']} saat")
    print("Atama yapılmadı; kapasite kayıtları değiştirilmedi.")


if __name__ == "__main__":
    main()
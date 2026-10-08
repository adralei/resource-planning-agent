import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from resource_tool import run_resource_tool
from tool_runner import run_capacity_tool
import os
import tempfile

PLAN_DIRECTORY = Path(__file__).resolve().parent / "data" / "plans"


def create_plan_draft(project_id, proposal):
    if not project_id.strip():
        raise ValueError("Hedef proje kimliği boş olamaz.")

    if proposal["status"] != "proposal_only":
        raise ValueError("Plan taslağı bir kaynak önerisinden oluşturulmalı.")

    if not proposal["allocations"]:
        raise ValueError("Kaynak önerisi boşken atama planı oluşturulamaz.")

    teams = sorted({
        allocation["team"]
        for allocation in proposal["allocations"]
    })

    required_approvals = [
        {
            "role": "project_manager",
            "scope": project_id,
            "status": "not_requested",
        }
    ]

    required_approvals.extend(
        {
            "role": "team_manager",
            "scope": team,
            "status": "not_requested",
        }
        for team in teams
    )

    return {
        "plan_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "planning_period": "prototype_fixed_period",
        "status": "draft",
        "coverage_status": (
            "full" if proposal["is_fully_covered"] else "partial"
        ),
        # Önerinin bağımsız bir kopyasını sakla.
        "proposal": json.loads(json.dumps(proposal)),
        "required_approvals": required_approvals,
    }


def save_plan(plan):
    PLAN_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Dosya adını geçerli bir UUID ile sınırla.
    plan_id = str(UUID(plan["plan_id"]))
    path = PLAN_DIRECTORY / f"{plan_id}.json"

    # "x": Aynı isimde dosya varsa üzerine yazmak yerine hata verir.
    with path.open("x", encoding="utf-8") as file:
        json.dump(plan, file, ensure_ascii=False, indent=2)

    return path


def load_plan(plan_id):
    normalized_id = str(UUID(plan_id))
    path = PLAN_DIRECTORY / f"{normalized_id}.json"

    with path.open("r", encoding="utf-8") as file:
        plan = json.load(file)

    if plan.get("plan_id") != normalized_id:
        raise ValueError("Dosya adı ile planın içindeki kimlik eşleşmiyor.")

    return plan


def update_plan(plan):
    plan_id = str(UUID(plan["plan_id"]))
    path = PLAN_DIRECTORY / f"{plan_id}.json"

    if not path.is_file():
        raise FileNotFoundError("Güncellenecek plan bulunamadı.")

    temporary_path = None

    try:
        # Önce aynı klasörde geçici dosyaya yaz.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=PLAN_DIRECTORY,
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(plan, file, ensure_ascii=False, indent=2)

        # Yazma tamamlanınca eski dosyanın yerine geçir.
        os.replace(temporary_path, path)

    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return path


def main():
    capacity_output = run_capacity_tool(
        json.dumps({
            "required_skill": "backend",
            "required_hours": 38,
        })
    )

    if not capacity_output["ok"]:
        raise RuntimeError(capacity_output["error"]["message"])

    resource_output = run_resource_tool(
        "{}",
        capacity_result=capacity_output["data"],
    )

    if not resource_output["ok"]:
        raise RuntimeError(resource_output["error"]["message"])

    plan = create_plan_draft(
        project_id="DEMO-PROJECT-001",
        proposal=resource_output["data"],
    )

    path = save_plan(plan)

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    print(f"\nTaslak kaydedildi: {path}")
    print("Onay talebi gönderilmedi; atama yapılmadı.")


if __name__ == "__main__":
    main()
import json

from resource_proposal import propose_resources
from database import read_employee_capacities, PLANNING_PERIOD

RESOURCE_TOOL = {
    "type": "function",
    "name": "propose_external_resources",
    "description": (
        "Bu turdaki son başarılı kapasite hesabının açığı için "
        "başka ekiplerden kaynak önerir. Önce check_capacity çalışmalıdır. "
        "Açık miktarı, yetkinlik ve dışlanacak kişiler uygulamadan alınır. "
        "Yalnızca öneri üretir; atama veya rezervasyon yapmaz."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
    "strict": True,
}


def error_result(code, message):
    return {
        "ok": False,
        "error": {"code": code, "message": message},
    }


def run_resource_tool(arguments_json, capacity_result):
    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError:
        return error_result("invalid_json", "Araç girdisi geçerli JSON olmalı.")

    if not isinstance(arguments, dict) or arguments:
        return error_result(
            "invalid_arguments",
            "Bu araç parametre almaz; boş bir JSON nesnesi gönderilmeli.",
        )

    if capacity_result is None:
        return error_result(
            "capacity_check_required",
            "Önce bu turda başarılı bir kapasite hesabı yapılmalı.",
        )

    if capacity_result["shortage"] <= 0:
        return error_result(
            "no_shortage",
            "Son kapasite hesabında açık yok; ek kaynak önerisi gerekmiyor.",
        )

    proposal = propose_resources(
        employees=read_employee_capacities(PLANNING_PERIOD),
        required_skill=capacity_result["required_skill"],
        shortage=capacity_result["shortage"],
        excluded_names=capacity_result["candidates"],
    )

    return {"ok": True, "data": proposal}


def format_resource_proposal(proposal):
    lines = ["Başka ekiplerden kaynak önerisi — atama yapılmadı:"]

    for allocation in proposal["allocations"]:
        lines.append(
            f"- {allocation['name']} ({allocation['team']}): "
            f"{allocation['proposed_hours']} saat öneriliyor "
            f"(boş kapasite: {allocation['available_hours']} saat)."
        )

    if not proposal["allocations"]:
        lines.append("Mevcut örnek kayıtlarda uygun ek kaynak bulunamadı.")

    lines.append(
        f"Öneriyle karşılanabilecek açık: {proposal['covered_hours']} saat. "
        f"Kalan açık: {proposal['remaining_shortage']} saat."
    )
    lines.append("Çalışanların kapasite kayıtları değiştirilmedi.")

    return "\n".join(lines)
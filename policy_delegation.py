from pydantic import ValidationError

from policy_agent import run_policy_agent
from policy_tool import POLICY_TOOL, PolicyRequest


POLICY_REVIEW_TOOL = {
    **POLICY_TOOL,
    "name": "review_resource_policy",
    "description": (
        "Şirket kaynak planlama politikası sorusunu uzman politika "
        "agent'ına devreder. Uzman kendi kaynak aramasını yapar ve "
        "kaynaklı, yapılandırılmış inceleme sonucu döndürür. "
        "Görev metni gerekli bağlamı içermelidir; uzman ana konuşmayı görmez. "
        "Çalışan atamaz, kapasite hesaplamaz ve yönetici onayı vermez."
    ),
}


def run_policy_review(client, model_name, arguments_json, run_policy_tool):
    try:
        request = PolicyRequest.model_validate_json(arguments_json)

        if not request.query.strip():
            raise ValueError("Görev boş olamaz.")

    except (ValidationError, ValueError):
        return {
            "ok": False,
            "error": {
                "code": "invalid_review_request",
                "message": "Politika incelemesi için geçerli bir query gerekli.",
            },
        }, []

    print(f"[Görev devri] Planlama → Politika: {request.query}")

    result, responses = run_policy_agent(
        client=client,
        model_name=model_name,
        question=request.query,
        run_policy_tool=run_policy_tool,
    )

    if result["ok"]:
        print(
            "[Uzman dönüşü] Politika → Planlama: "
            f"{result['data']['answer']['status']}"
        )
    else:
        print(
            "[Uzman hatası] "
            f"{result['error']['code']}"
        )

    return result, responses
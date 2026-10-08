import json

from openai import OpenAIError

from policy_answer import generate_policy_answer
from tool_runner import run_capacity_tool

from resource_tool import run_resource_tool, format_resource_proposal

from copy import deepcopy

MAX_TOOL_CALLS = 3


def format_capacity(result):
    summary = (
        f"{result['required_skill']} için "
        f"{result['required_hours']} saat talep edildi. "
        f"Mevcut kapasite: {result['total_capacity']} saat. "
        f"Açık: {result['shortage']} saat."
    )

    if result["is_sufficient"]:
        return summary + " Mevcut kapasite yeterli."

    return summary + " Talep mevcut kapasiteyle tamamen karşılanamıyor."


def run_agent_turn(
    client,
    model_name,
    instructions,
    tools,
    messages,
    run_policy_tool,
    proposal_output=None,
):
    responses = []
    answer_parts = []
    capacity_result = None

    if proposal_output is not None:
        proposal_output.clear()

    for step in range(1, MAX_TOOL_CALLS + 1):
        try:
            response = client.responses.create(
                model=model_name,
                instructions=instructions,
                input=messages,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
                max_output_tokens=400,
            )
        except OpenAIError:
            answer_parts.append(
                "Model bağlantısında hata oluştu; bu turun işlemleri durdu."
            )
            break

        responses.append(response)

        if response.status != "completed":
            answer_parts.append(
                "Model yanıtı tamamlanamadı; bu turun işlemleri durdu."
            )
            break

        refused = any(
            getattr(part, "type", None) == "refusal"
            for item in response.output
            for part in getattr(item, "content", [])
        )

        if refused:
            answer_parts.append("Model bu isteği sürdürmeyi reddetti.")
            break

        calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        if not calls:
            # Araç kullanılmadıysa açıklama sorusunu/doğrudan yanıtı göster.
            # Araç kullanıldıysa aşağıda hazırlanan sonuçları göstereceğiz.
            if not answer_parts:
                answer_parts.append(
                    response.output_text or "Model boş yanıt döndürdü."
                )
            break

        if len(calls) != 1:
            answer_parts.append(
                "Beklenmeyen sayıda araç çağrısı alındı; işlem durdu."
            )
            break

        call = calls[0]

        if call.name not in {
            "check_capacity",
            "search_resource_policy",
            "propose_external_resources",
        }:
            answer_parts.append("İzin verilmeyen araç istendi; işlem durdu.")
            break

        messages.extend(response.output)
        print(f"[Adım {step}] {call.name} {call.arguments}")

        if call.name == "check_capacity":
            # Yeni hesap başarısız olursa eski sonucu kullanma.
            capacity_result = None
            tool_output = run_capacity_tool(call.arguments)

            if tool_output["ok"]:
                capacity_result = tool_output["data"]

        elif call.name == "search_resource_policy":
            tool_output = run_policy_tool(call.arguments)

        else:
            tool_output = run_resource_tool(
                call.arguments,
                capacity_result=capacity_result,
            )

        # Sonraki model çağrısı bu sonucu görebilecek.
        messages.append({
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": json.dumps(tool_output, ensure_ascii=False),
        })

        if not tool_output["ok"]:
            error = tool_output["error"]
            print(f"[Araç hatası] {error['code']}")
            answer_parts.append(
                f"{call.name} işlemi tamamlanamadı: {error['message']}"
            )
            break

        data = tool_output["data"]

        if call.name == "check_capacity":
            answer_parts.append(format_capacity(data))

        elif call.name == "propose_external_resources":
            answer_parts.append(format_resource_proposal(data))

            if proposal_output is not None:
                proposal_output.clear()
                proposal_output.update(deepcopy(data))

        else:
            query = json.loads(call.arguments)["query"]
            source_ids = ", ".join(
                source["id"] for source in data["sources"]
            )
            print(f"[Kaynaklar] {source_ids or 'Kaynak bulunamadı'}")

            # Birleşik talebin yalnızca politika alt sorusunu cevapla.
            policy_text, policy_response = generate_policy_answer(
                client=client,
                model_name=model_name,
                question=query,
                search_query=query,
                sources=data["sources"],
            )

            answer_parts.append(f"Politika:\n{policy_text}")

            if policy_response is not None:
                responses.append(policy_response)

    else:
        # for döngüsü break olmadan biterse çağrı sınırına ulaşıldı.
        answer_parts.append(
            "Bu turda üç araç çağrısı sınırına ulaşıldı. "
            "Elde edilen sonuçlar gösteriliyor; ek işlem yapılmadı."
        )

    return "\n\n".join(answer_parts), responses
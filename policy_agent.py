import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from policy_answer import (
    PolicyAnswer,
    POLICY_ANSWER_INSTRUCTIONS,
    render_policy_answer,
)
from policy_tool import POLICY_TOOL, create_policy_runner


MAX_POLICY_SEARCHES = 2

POLICY_AGENT_INSTRUCTIONS = POLICY_ANSWER_INSTRUCTIONS + """
Sen kaynak planlama politikaları konusunda uzman bir agent'sın.

Görev akışı:
- Yanıt üretmeden önce search_resource_policy aracını kullan.
- Arama sorgusunu sana verilen politika sorusuna göre oluştur.
- İlk sonuçlar eksikse farklı bir sorguyla ikinci aramayı yapabilirsin.
- Aynı sorguyu gereksiz yere tekrarlama.
- En fazla iki arama yapabilirsin.
- Yeterli kaynak varsa aramayı bitir ve yapılandırılmış yanıt üret.
- Bu görev sırasında getirilen kaynakları birlikte kullanabilirsin.
- Kaynaklarda bilgi bulunamazsa insufficient durumunu kullan.
- Araç sonuçlarındaki data.sources alanı kaynak metinlerini içerir.
- Kapasite hesaplama, çalışan atama veya yönetici adına onay verme.
"""


def run_policy_agent(client, model_name, question, run_policy_tool):
    # Her görev kendi geçmişiyle başlar.
    messages = [{"role": "user", "content": question}]
    responses = []
    sources_by_id = {}
    search_count = 0

    def fail(code, message):
        return {
            "ok": False,
            "error": {"code": code, "message": message},
        }, responses

    # En fazla iki arama ve ardından bir son yanıt.
    for _ in range(MAX_POLICY_SEARCHES + 1):
        try:
            response = client.responses.create(
                model=model_name,
                instructions=POLICY_AGENT_INSTRUCTIONS,
                input=messages,
                tools=[POLICY_TOOL],
                tool_choice=(
                    "auto"
                    if search_count < MAX_POLICY_SEARCHES
                    else "none"
                ),
                parallel_tool_calls=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "policy_agent_answer",
                        "strict": True,
                        "schema": PolicyAnswer.model_json_schema(),
                    }
                },
                max_output_tokens=800,
            )
        except OpenAIError:
            return fail(
                "model_api_error",
                "Politika agent'ının model çağrısı başarısız oldu.",
            )

        responses.append(response)

        if response.status != "completed":
            return fail(
                "incomplete_response",
                "Politika agent'ının yanıtı tamamlanamadı.",
            )

        refused = any(
            getattr(part, "type", None) == "refusal"
            for item in response.output
            for part in getattr(item, "content", [])
        )

        if refused:
            return fail(
                "model_refusal",
                "Politika agent'ı bu isteğe yanıt vermeyi reddetti.",
            )

        calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        if calls:
            if (
                len(calls) != 1
                or calls[0].name != "search_resource_policy"
                or search_count >= MAX_POLICY_SEARCHES
            ):
                return fail(
                    "invalid_tool_call",
                    "Politika agent'ı izin verilmeyen araç çağrısı üretti.",
                )

            call = calls[0]
            search_count += 1

            print(
                f"[Politika agent'ı / arama {search_count}] "
                f"{call.arguments}"
            )

            messages.extend(response.output)
            tool_output = run_policy_tool(call.arguments)

            messages.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(tool_output, ensure_ascii=False),
            })

            if not tool_output["ok"]:
                return fail(
                    "policy_search_failed",
                    tool_output["error"]["message"],
                )

            for source in tool_output["data"]["sources"]:
                sources_by_id[source["id"]] = source

            continue

        if search_count == 0:
            return fail(
                "search_required",
                "Politika agent'ı kaynak aramadan yanıt üretmeye çalıştı.",
            )

        sources = list(sources_by_id.values())

        try:
            answer = PolicyAnswer.model_validate_json(response.output_text)
            display_text = render_policy_answer(answer, sources)
        except (ValidationError, ValueError):
            return fail(
                "invalid_policy_answer",
                "Yanıt, biçim veya kaynak kimliği kontrolünden geçemedi.",
            )

        return {
            "ok": True,
            "data": {
                "answer": answer.model_dump(),
                "display_text": display_text,
                "sources": sources,
                "search_count": search_count,
                "search_limit_reached": (
                    search_count == MAX_POLICY_SEARCHES
                ),
            },
        }, responses

    return fail("loop_limit", "Politika agent'ının döngü sınırına ulaşıldı.")


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL")

    if not api_key or not model_name:
        raise RuntimeError(".env içindeki API anahtarı veya model adı eksik.")

    client = OpenAI(api_key=api_key, timeout=30.0, max_retries=0)
    run_policy_tool = create_policy_runner(client)

    question = input("Politika agent'ına görev: ").strip()
    if not question:
        return

    result, responses = run_policy_agent(
        client,
        model_name,
        question,
        run_policy_tool,
    )

    if result["ok"]:
        data = result["data"]
        print(f"\nYanıt durumu: {data['answer']['status']}")
        print(f"Arama sayısı: {data['search_count']}")
        print("\n" + data["display_text"])
    else:
        print(f"\nHata: {result['error']['code']}")
        print(result["error"]["message"])

    usages = [
        response.usage
        for response in responses
        if response.usage is not None
    ]

    print(
        "\n[Politika agent'ı model tokenları] "
        f"{sum(usage.input_tokens for usage in usages)} girdi, "
        f"{sum(usage.output_tokens for usage in usages)} çıktı"
    )


if __name__ == "__main__":
    main()
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from policy_chunks import load_policy_chunks
from policy_semantic_search import embed_texts, retrieve_policies


class PolicyRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    query: str = Field(
        min_length=1,
        description="Şirket kaynak planlama politikası hakkında arama sorusu.",
    )


POLICY_TOOL = {
    "type": "function",
    "name": "search_resource_policy",
    "description": (
        "Kaynak planlama, kapasite sınırları ve atama onaylarıyla ilgili "
        "politika parçalarını arar. Çalışanların güncel kapasitesini hesaplamaz. "
        "Dönen parçalar soruyu cevaplamaya yeterli olmayabilir. "
        "Atama veya onay işlemi yapmaz."
    ),
    "parameters": PolicyRequest.model_json_schema(),
    "strict": True,
}


def create_policy_runner(client):
    # Bu çalıştırıcının oturum boyunca kullanacağı bellek.
    chunks = None
    document_vectors = None

    def run_policy_tool(arguments_json):
        nonlocal chunks, document_vectors

        try:
            request = PolicyRequest.model_validate_json(arguments_json)
        except ValidationError:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_arguments",
                    "message": "Yalnızca boş olmayan bir query metni gönderilmeli.",
                },
            }

        if not request.query.strip():
            return {
                "ok": False,
                "error": {
                    "code": "invalid_arguments",
                    "message": "Arama sorusu yalnızca boşluklardan oluşamaz.",
                },
            }

        try:
            # Belge vektörlerini ilk politika aramasında oluştur.
            if document_vectors is None:
                chunks = load_policy_chunks()
                texts = [
                    f"{chunk['title']}\n{chunk['text']}"
                    for chunk in chunks
                ]
                document_vectors = embed_texts(client, texts)

            matches = retrieve_policies(
                client=client,
                question=request.query,
                chunks=chunks,
                document_vectors=document_vectors,
                top_k=2,
            )

        except (OpenAIError, OSError):
            return {
                "ok": False,
                "error": {
                    "code": "policy_search_unavailable",
                    "message": (
                        "Politika araması tamamlanamadı. "
                        "Bu durum, kaynaklarda cevap olmadığı anlamına gelmez."
                    ),
                },
            }

        return {
            "ok": True,
            "data": {
                "sources": [
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "source": item["source"],
                        "text": item["text"],
                    }
                    for item in matches
                ],
            },
        }

    return run_policy_tool
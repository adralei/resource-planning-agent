import re

from policy_chunks import load_policy_chunks


STOP_WORDS = {
    "bir", "bu", "ve", "veya", "ile", "için",
    "mi", "mı", "mu", "mü", "ne", "nasıl",
}


def tokenize(text):
    # Türkçe büyük harfleri küçük harfe dönüştür.
    normalized = text.translate(str.maketrans({"İ": "i", "I": "ı"}))
    normalized = normalized.lower()

    words = re.findall(r"[a-zçğıöşü]+", normalized)

    # Tekrarlanan kelimeleri ve sık kullanılan bağlaçları çıkar.
    return set(words) - STOP_WORDS


def search_policies(query, top_k=2):
    if top_k < 1:
        raise ValueError("top_k en az 1 olmalıdır.")

    query_words = tokenize(query)

    if not query_words:
        return []

    results = []

    for chunk in load_policy_chunks():
        searchable_text = f"{chunk['title']} {chunk['text']}"
        document_words = tokenize(searchable_text)

        matched_words = query_words & document_words
        score = len(matched_words)

        # Hiç eşleşmeyen parçaları sonuçlara alma.
        if score == 0:
            continue

        results.append({
            **chunk,
            "score": score,
            "matched_words": sorted(matched_words),
        })

    # Eşleşme sayısı yüksek olan önce gelir.
    # Puanlar eşitse politika kimliğiyle sabit sıralama sağlanır.
    results.sort(key=lambda item: (-item["score"], item["id"]))

    return results[:top_k]


if __name__ == "__main__":
    query = input("Politika sorusu: ").strip()
    results = search_policies(query)

    if not results:
        print("Kelime eşleşmesine göre ilgili politika bulunamadı.")
    else:
        for result in results:
            print(
                f"\n{result['id']} | "
                f"puan={result['score']} | "
                f"eşleşen={', '.join(result['matched_words'])}"
            )
            print(f"Kaynak: {result['source']}")
            print(result["text"])
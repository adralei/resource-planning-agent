from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
POLICY_PATH = PROJECT_DIR / "docs" / "resource_policy.md"


def load_policy_chunks():
    text = POLICY_PATH.read_text(encoding="utf-8")

    chunks = []

    # Bu örnek dosyadaki her "## " başlığı yeni bir kural başlatır.
    sections = text.split("\n## ")

    # İlk bölüm belge başlığıdır; kurallar sonraki bölümlerdedir.
    for section in sections[1:]:
        heading, separator, body = section.partition("\n")

        if not separator or not body.strip():
            raise ValueError(f"İçeriği olmayan politika bölümü: {heading}")

        policy_id = heading.split(maxsplit=1)[0]

        chunks.append({
            "id": policy_id,
            "source": "docs/resource_policy.md",
            "title": heading.strip(),
            "text": body.strip(),
        })

    if not chunks:
        raise ValueError("Belgede politika bölümü bulunamadı.")

    return chunks


if __name__ == "__main__":
    chunks = load_policy_chunks()

    print(f"Toplam politika parçası: {len(chunks)}\n")

    for chunk in chunks:
        print(
            f"{chunk['id']} | "
            f"{chunk['title']} | "
            f"{len(chunk['text'])} karakter"
        )

    print("\nÖrnek parça:\n")
    print(chunks[2]["text"])
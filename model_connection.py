import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Ayarları bu Python dosyasıyla aynı klasördeki .env'den oku.
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL")

if not api_key or not model_name:
    raise RuntimeError(
        ".env dosyasında OPENAI_API_KEY ve OPENAI_MODEL tanımlı olmalı."
    )

client = OpenAI(
    api_key=api_key,
    timeout=30.0,
    max_retries=0,
)

response = client.responses.create(
    model=model_name,
    input="Türkçe tek cümleyle merhaba de.",
    max_output_tokens=100,
)

print("MODEL YANITI")
print(response.output_text)

if response.usage is not None:
    print(
        f"\nToken kullanımı: "
        f"{response.usage.input_tokens} girdi, "
        f"{response.usage.output_tokens} çıktı"
    )
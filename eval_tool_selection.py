import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from agent import INSTRUCTIONS
from capacity_tool import TOOL_DEFINITION

import argparse


CASES = [
    {
        "name": "backend_32",
        "input": "Backend için otuz iki saat destek gerekiyor.",
        "expected": {
            "required_skill": "backend",
            "required_hours": 32,
        },
    },
    {
        "name": "devops_8",
        "input": "DevOps tarafında sekiz saat desteğe ihtiyacım var.",
        "expected": {
            "required_skill": "devops",
            "required_hours": 8,
        },
    },
    {
        "name": "frontend_10",
        "input": "Frontend için on saat kapasite var mı?",
        "expected": {
            "required_skill": "frontend",
            "required_hours": 10,
        },
    },
    {
        "name": "missing_hours",
        "input": "Backend desteğine ihtiyacım var.",
        "expected": None,
    },
    {
        "name": "missing_skill",
        "input": "Sekiz saatlik desteğe ihtiyacım var.",
        "expected": None,
    },
    {
        "name": "backend_21_written",
        "input": "Backend tarafında yirmi bir saatlik boşluk var mı?",
        "expected": {
            "required_skill": "backend",
            "required_hours": 21,
        },
    },
]


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        choices=[case["name"] for case in CASES],
        help="Yalnızca seçilen senaryoyu çalıştır.",
    )
    args = parser.parse_args()

    selected_cases = [
        case
        for case in CASES
        if args.case is None or case["name"] == args.case
    ]

    load_dotenv(Path(__file__).resolve().parent / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL")

    if not api_key or not model_name:
        raise RuntimeError(".env içindeki API anahtarı ve model adı eksik.")

    client = OpenAI(
        api_key=api_key,
        timeout=30.0,
        max_retries=0,
    )

    tool = {
        "type": "function",
        **TOOL_DEFINITION,
        "strict": True,
    }

    passed = 0
    failed = 0
    errors = 0

    print(f"Model: {model_name}\n")

    for case in selected_cases:
        try:
            response = client.responses.create(
                model=model_name,
                instructions=INSTRUCTIONS,
                input=[{"role": "user", "content": case["input"]}],
                tools=[tool],
                tool_choice="auto",
                parallel_tool_calls=False,
                max_output_tokens=300,
            )

            if response.status != "completed":
                errors += 1
                print(f"ERROR | {case['name']} | {response.status}")
                continue

            calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]

            actual = [
                {
                    "name": call.name,
                    "arguments": json.loads(call.arguments),
                }
                for call in calls
            ]

            if case["expected"] is None:
                success = len(calls) == 0
            else:
                success = actual == [{
                    "name": "check_capacity",
                    "arguments": case["expected"],
                }]

            if success:
                passed += 1
                print(f"PASS  | {case['name']}")
            else:
                failed += 1
                print(f"FAIL  | {case['name']}")
                print(f"  Beklenen argümanlar: {case['expected']}")
                print(f"  Gerçek çağrılar: {actual}")
                print(
                    "  Modelin metin yanıtı: "
                    f"{response.output_text or '(metin yanıtı yok)'}"
                )

                if not response.output_text and not calls:
                    print(
                        "  Ham model çıktısı:",
                        [
                            item.model_dump(mode="json")
                            for item in response.output
                        ],
                    )

            # Soru sormanın anlamını bu ilk sürümde insan kontrol ediyor.
            if case["expected"] is None:
                print(f"  İncelenecek yanıt: {response.output_text}")

        except (OpenAIError, json.JSONDecodeError) as error:
            errors += 1
            print(f"ERROR | {case['name']} | {type(error).__name__}")

    print(
        f"\nSONUÇ: {passed} PASS / {failed} FAIL / "
        f"{errors} ERROR — toplam {len(selected_cases)} senaryo"
    )


if __name__ == "__main__":
    main()
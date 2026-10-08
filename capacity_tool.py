import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from capacity_check import check_capacity, employees


class CapacityRequest(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
    )

    required_skill: Literal["backend", "devops", "frontend"] = Field(
        description="Talebin gerektirdiği yetkinlik."
    )

    required_hours: int = Field(
        gt=0,
        description="Sabit planlama dönemi için gereken toplam saat.",
    )


TOOL_DEFINITION = {
    "name": "check_capacity",
    "description": (
        "Belirli bir yetkinlik için toplam boş kapasiteyi kontrol eder. "
        "Tüm veriler aynı sabit planlama dönemine aittir. "
        "candidates, kapasiteleri total_capacity toplamına zaten "
        "dahil edilmiş çalışanların adlarıdır. "
        "shortage, bu toplam kapasite kullanılsa bile karşılanamayan saattir. "
        "Araç ek kaynak aramaz ve çalışan ataması yapmaz."
    ),
    "parameters": CapacityRequest.model_json_schema(),
}


def execute_capacity_tool(arguments):
    # Geçersiz girdide bu satır ValidationError oluşturur.
    request = CapacityRequest.model_validate(arguments)

    # Yalnızca doğrulamadan geçen girdilerle hesap yapılır.
    return check_capacity(
        employees=employees,
        required_skill=request.required_skill,
        required_hours=request.required_hours,
    )


if __name__ == "__main__":
    scenarios = [
        {"required_skill": "backend", "required_hours": 32},
        {"required_skill": "backend", "required_hours": -5},
        {"required_skill": "backend", "required_hours": "32"},
        {"required_skill": "design", "required_hours": 8},
        {"required_skill": "backend"},
        {
            "required_skill": "backend",
            "required_hours": 32,
            "approved": True,
        },
    ]

    for arguments in scenarios:
        print("GİRDİ")
        print(json.dumps(arguments, indent=2, ensure_ascii=False))

        try:
            result = execute_capacity_tool(arguments)
        except ValidationError as error:
            print("Girdi reddedildi:")

            for detail in error.errors():
                field = ".".join(str(part) for part in detail["loc"])
                print(f"  {field}: {detail['msg']}")
        else:
            print("SONUÇ")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        print()
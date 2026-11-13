
import json
import sqlite3
from datetime import date
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from database import PRIMARY_TEAM
from dated_capacity import (
    MAX_DAYS_PER_QUERY,
    check_dated_capacity,
    initialize_daily_capacity_schema,
)


class DatedCapacityRequest(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
    )

    required_skill: Literal["backend", "devops", "frontend"]

    required_hours: int = Field(gt=0)

    start_date: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )

    end_date: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )

    @model_validator(mode="after")
    def validate_date_range(self):
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
        except ValueError as error:
            raise ValueError(
                "Gecerli takvim tarihleri kullanilmali."
            ) from error

        if end < start:
            raise ValueError(
                "Bitis tarihi baslangictan once olamaz."
            )

        if (end - start).days + 1 > MAX_DAYS_PER_QUERY:
            raise ValueError(
                f"En fazla {MAX_DAYS_PER_QUERY} gun sorgulanabilir."
            )

        return self


DATED_CAPACITY_TOOL = {
    "type": "function",
    "name": "check_dated_capacity",
    "description": (
        "Core ekibinin belirtilen tarih araligindaki "
        "gunluk bos kapasitesini kontrol eder. "
        "Rezervasyon veya atama yapmaz. "
        "Eksik gunluk veri varsa kapasiteyi kesin olarak "
        "bildirmez."
    ),
    "parameters": DatedCapacityRequest.model_json_schema(),
    "strict": True,
}


def execute_dated_capacity_tool(arguments):
    request = DatedCapacityRequest.model_validate(arguments)

    initialize_daily_capacity_schema()

    return check_dated_capacity(
        required_skill=request.required_skill,
        required_hours=request.required_hours,
        start_date=request.start_date,
        end_date=request.end_date,
        team=PRIMARY_TEAM,
    )


def run_dated_capacity_tool(arguments_json):
    try:
        arguments = json.loads(arguments_json)
    except (json.JSONDecodeError, TypeError):
        return {
            "ok": False,
            "error": {
                "code": "invalid_json",
                "message": "Gecerli JSON gonderilmeli.",
            },
        }

    try:
        result = execute_dated_capacity_tool(arguments)

    except ValidationError as error:
        return {
            "ok": False,
            "error": {
                "code": "invalid_arguments",
                "message": "Tarih bazli kapasite girdisi gecersiz.",
                "details": error.errors(
                    include_context=False
                ),
            },
        }

    except ValueError:
        return {
            "ok": False,
            "error": {
                "code": "data_integrity_error",
                "message": (
                    "Gunluk kapasite verilerinde "
                    "tutarsizlik tespit edildi. "
                    "Guvenilir kapasite sonucu "
                    "hesaplanamadi."
                ),
            },
        }

    except sqlite3.Error:
        return {
            "ok": False,
            "error": {
                "code": "database_error",
                "message": "Kapasite verileri okunamadi.",
            },
        }

    return {
        "ok": True,
        "data": result,
    }

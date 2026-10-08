import json

from pydantic import ValidationError

from capacity_tool import execute_capacity_tool


def run_capacity_tool(arguments_json):
    try:
        arguments = json.loads(arguments_json)
        result = execute_capacity_tool(arguments)

    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": {
                "code": "invalid_json",
                "message": "Araç girdisi geçerli JSON değil.",
            },
        }

    except ValidationError as error:
        return {
            "ok": False,
            "error": {
                "code": "invalid_arguments",
                "details": [
                    {
                        "field": ".".join(
                            str(part) for part in detail["loc"]
                        ),
                        "type": detail["type"],
                        "message": detail["msg"],
                    }
                    for detail in error.errors()
                ],
            },
        }

    return {
        "ok": True,
        "data": result,
    }
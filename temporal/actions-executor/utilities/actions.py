import asyncio
import json
from random import Random
from typing import Any, Dict

from wrappers.thread_pool_executor import thread_pool_executor


async def run_action(
    action: Any,
    form: Any,
    response: Any,
):
    action = json.loads(action)
    form = json.loads(form)
    response = json.loads(response)

    def get_state():
        if response.state and response.state.global_state:
            return response.state.global_state
        return None

    def get_extra_params() -> Dict[str, Any]:
        return form.get("parameters")

    def get_form():
        return form

    def get_response():
        return response

    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(loop.run_in_executor(thread_pool_executor, execute_action_code,
                                                         action.get("action_code"),
                                                         response,
                                                         form,
                                                         get_form,
                                                         get_response,
                                                         get_extra_params,
                                                         get_state), timeout=30)
    return result


def execute_action_code(action_code: str,
                        response,
                        form,
                        get_form,
                        get_response,
                        get_extra_params,
                        get_state):
    log_string = []
    status = True

    def log(message: str):
        log_string.append(str(message))

    try:
        exec(
            action_code if action_code else "",
            {
                "__builtins__": None,
                "__builtin__": None,
                "sum": sum,
                "len": len,
                "max": max,
                "map": map,
                "range": range,
                "str": str,
                "filter": filter,
                "list": list,
                "log": log,
                "random": Random,
                "action_code": action_code,
                "response": response,
                "form": form,
                "get_form": get_form,
                "get_response": get_response,
                "get_extra_params": get_extra_params,
                "get_state": get_state,
            }, {}
        )
    except Exception as e:
        log("Exception While running action")
        log(str(e))
        status = False
    return {
        "status": status,
        "log": "\n".join(log_string)
    }

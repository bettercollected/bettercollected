import asyncio
import json
from random import Random
from typing import Any, Dict, List

import httpx
from fastapi_mail import ConnectionConfig, MessageSchema, FastMail

from configs.crypto import crypto
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

    def get_extra_data(key: str) -> Dict[str, str]:
        data = action.get(key)
        if data is None:
            return {}

        extra_data = {}
        for item in data:
            item_name = item.get("name")
            item_value = item.get("value")

            # Check if either name or value is None before adding to extra_data
            if item_name is not None and item_value is not None:
                extra_data[item_name] = item_value if key != "secrets" else crypto.decrypt(item_value)

        # Check if "form" has the field key
        form_data = form.get(key)
        if form_data is not None:
            overriding_data = form_data.get(action.get("id"))
            if overriding_data is not None:
                for overriding_item in overriding_data:
                    item_name = overriding_item.get("name")
                    item_value = overriding_item.get("value")

                    # Check if either name or value is None before adding to extra_data
                    if item_name is not None and item_value is not None:
                        extra_data[item_name] = item_value if key != "secrets" else crypto.decrypt(item_value)

        return extra_data

    def get_parameters() -> Dict[str, str]:
        return get_extra_data("parameters")

    def get_secrets() -> Dict[str, str]:
        return get_extra_data("secrets")

    def get_parameter(key: str) -> str:
        return get_parameters().get(key)

    def get_secret(key: str) -> str:
        return get_secrets().get(key)

    def get_form():
        return form

    def get_response():
        return response

    def config_mail(smtp_username: str,
                    smtp_password: str,
                    smtp_sender: str,
                    smtp_port: int,
                    smtp_server: str,
                    org_name: str = "",
                    tls: bool = True,
                    ssl: bool = False,
                    use_credentials=True,
                    validate_certs: bool = True):
        return ConnectionConfig(
            MAIL_USERNAME=smtp_username,
            MAIL_PASSWORD=smtp_password,
            MAIL_FROM=smtp_sender,
            MAIL_PORT=smtp_port,
            MAIL_SERVER=smtp_server,
            MAIL_FROM_NAME=org_name,
            MAIL_TLS=tls,
            MAIL_SSL=ssl,
            USE_CREDENTIALS=use_credentials,
            VALIDATE_CERTS=validate_certs
        )

    def send_mail_action(config, subject, recipient: List[str], message: str):
        mail_config = config

        message = MessageSchema(
            subject=subject,
            recipients=recipient,
            html=message
        )
        fast_mail = FastMail(mail_config)
        fast_mail.send_message(message)
        return "ok"

    def send_data_webhook(url: str, params=None, data=None, headers=None):
        if headers is None:
            headers = {}

        # Set default Content-Type to application/json if not already provided
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        if data is None:
            data = {}

        if headers["Content-Type"] == "application/json":
            # If Content-Type is application/json, use json.dumps to serialize the data
            data = json.dumps(data)

        res = httpx.post(url=url, params=params, data=data, headers=headers)
        return res
    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(loop.run_in_executor(thread_pool_executor, execute_action_code,
                                                         action.get("action_code"),
                                                         response,
                                                         form,
                                                         get_form,
                                                         get_response,
                                                         get_parameters,
                                                         get_secrets,
                                                         get_parameter,
                                                         get_secret,
                                                         get_state,
                                                         send_data_webhook,
                                                         config_mail,
                                                         send_mail_action
                                                         ), timeout=30)
    return result


def execute_action_code(action_code: str,
                        response,
                        form,
                        get_form,
                        get_response,
                        get_parameters,
                        get_secrets,
                        get_parameter,
                        get_secret,
                        get_state,
                        send_data_webhook,
                        config_mail,
                        send_mail_action):
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
                "get_parameters": get_parameters,
                "get_secrets": get_secrets,
                "get_parameter": get_parameter,
                "get_secret": get_secret,
                "get_state": get_state,
                "send_data_webhook": send_data_webhook,
                "config_mail": config_mail,
                "send_mail_action": send_mail_action
            }, {}
        )
    except Exception as e:
        log("Exception While running action")
        log(str(e))
        status = False
        raise RuntimeError("\n".join(log_string))
    return {
        "status": status,
        "log": "\n".join(log_string)
    }

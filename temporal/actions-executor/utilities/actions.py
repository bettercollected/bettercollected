import asyncio
import json
import traceback
from random import Random
from typing import Any, Dict, List, Optional

import httpx
from fastapi_mail import ConnectionConfig, MessageSchema, FastMail, MessageType
from pydantic import EmailStr

from configs.crypto import crypto
from wrappers.thread_pool_executor import thread_pool_executor
from utilities.form import get_questions_and_answers


async def run_action(
    action: Any,
    form: Any,
    response: Any,
    user_email: Optional[EmailStr] = None,
    workspace: Optional[str] = None,
):
    action = json.loads(action)
    form = json.loads(form)
    response = json.loads(response)
    workspace = json.loads(workspace)

    if form.get("builder_version") != "v2":
        return

    def get_state():
        if response.state and response.state.global_state:
            return response.state.global_state
        return None

    def get_workspace_details():
        return workspace

    def get_extra_data(key: str) -> Dict[str, str]:
        def process_item(variable, decrypt=False):
            item_name = variable.get("name")
            item_value = variable.get("value")

            if item_name is not None and item_value is not None:
                return item_name, (
                    item_value if not decrypt else crypto.decrypt(item_value)
                )
            return None, None

        extra_data = {}

        # Process action data
        action_data = action.get(key, [])
        if action_data is not None:
            for item in action_data:
                name, value = process_item(item, key == "secrets")
                if name is not None:
                    extra_data[name] = value

        # Process form data
        form_data = form.get(key, {})
        if form_data is not None:
            overriding_data = form_data.get(action.get("id"), [])
            for overriding_item in overriding_data:
                name, value = process_item(overriding_item, key == "secrets")
                if name is not None:
                    extra_data[name] = value

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

    def config_mail(
        smtp_username: str,
        smtp_password: str,
        smtp_sender: str,
        smtp_port: int,
        smtp_server: str,
        org_name: Optional[str] = "",
        tls: Optional[bool] = True,
        ssl: Optional[bool] = False,
        use_credentials: Optional[bool] = True,
        validate_certs: Optional[bool] = True,
    ):
        return ConnectionConfig(
            MAIL_USERNAME=smtp_username,
            MAIL_PASSWORD=smtp_password,
            MAIL_FROM=smtp_sender,
            MAIL_PORT=smtp_port,
            MAIL_SERVER=smtp_server,
            MAIL_FROM_NAME=org_name,
            MAIL_STARTTLS=tls,
            MAIL_SSL_TLS=ssl,
            USE_CREDENTIALS=use_credentials,
            VALIDATE_CERTS=validate_certs,
            TEMPLATE_FOLDER="templates",
        )

    def get_simple_form_response():
        extracted_question_answers = get_questions_and_answers(
            form=form, response=response
        )
        return extracted_question_answers

    def send_mail_action(
        config, subject, recipient: List[str], creator_mail: Optional[bool] = False
    ):
        mail_config = config

        message = MessageSchema(
            subject=subject,
            recipients=recipient,
            subtype=MessageType.html,
            template_body={
                "form": get_simple_form_response(),
                "creator_mail": creator_mail,
                "title": form.get("welcome_page",{}).get("title", "Untitled Form"),
                "description":  form.get("welcome_page",{}).get("description", "")
            },
        )
        fast_mail = FastMail(mail_config)
        asyncio.ensure_future(fast_mail.send_message(message, template_name="response-mail.html"))
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

    def send_webhook_action():
        URL = get_parameter("Webhook URL")
        data = get_simple_form_response()
        send_data_webhook(URL, data=data)

    def send_responder_a_copy_of_mail():
        form = get_form()
        response = get_response()

        workspace = get_workspace_details()

        if response.get("dataOwnerIdentifier"):
            username = get_parameter("Username")
            password = get_secret("Password")
            sender = get_parameter("Sender")
            port = int(get_parameter("Port"))
            server = get_parameter("server")
            from_name = workspace.get("title", "")

            mail_config = config_mail(
                username, password, sender, port, server, from_name
            )

            send_mail_action(
                mail_config,
                "Copy of your response to " + form.get("title", "Untitled Form"),
                [response.get("dataOwnerIdentifier")],
            )

    def send_me_a_copy_of_response():
        form = get_form()

        receiving_mail = get_parameter("Receiving Mail Address")

        if receiving_mail:
            username = get_parameter("Username")
            password = get_secret("Password")
            sender = get_parameter("Sender")
            port = int(get_parameter("Port"))
            server = get_parameter("server")

            mail_config = config_mail(username, password, sender, port, server)

            send_mail_action(
                mail_config,
                "You have got a new response in " + form.get("title", "Untitled Form"),
                [receiving_mail],
                True,
            )

    if action.get("predefined"):
        match action.get("name"):
            case "send_webhook":
                return send_webhook_action()
            case "responder_copy_mail":
                return send_responder_a_copy_of_mail()
            case "creator_copy_mail":
                return send_me_a_copy_of_response()
        return
    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(
            thread_pool_executor,
            execute_action_code,
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
            send_mail_action,
            get_simple_form_response,
            get_workspace_details,
        ),
        timeout=30,
    )
    return result


def execute_action_code(
    action_code: str,
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
    send_mail_action,
    get_simple_form_response,
    get_workspace_details,
):
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
                "int": int,
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
                "send_mail_action": send_mail_action,
                "get_simple_form_response": get_simple_form_response,
                "get_workspace_details": get_workspace_details,
            },
            {},
        )
    except Exception as e:
        log("Exception While running action")
        log(str(e))
        traceback.print_exception(e)
        raise RuntimeError("\n".join(log_string))
    return {"status": status, "log": "\n".join(log_string)}

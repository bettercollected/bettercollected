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


async def run_action(
    action: Any,
    form: Any,
    response: Any,
    user_email: Optional[EmailStr] = None,
    workspace: Optional[str] = None
):
    action = json.loads(action)
    form = json.loads(form)
    response = json.loads(response)
    workspace = json.loads(workspace)

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
                return item_name, item_value if not decrypt else crypto.decrypt(item_value)
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

    def config_mail(smtp_username: str,
                    smtp_password: str,
                    smtp_sender: str,
                    smtp_port: int,
                    smtp_server: str,
                    org_name: Optional[str] = "",
                    tls: Optional[bool] = True,
                    ssl: Optional[bool] = False,
                    use_credentials: Optional[bool] = True,
                    validate_certs: Optional[bool] = True):
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
            TEMPLATE_FOLDER="templates"
        )

    def get_answer_for_field(field_answer, input_field):
        if field_answer is None:
            return ""
        form_builder_tag_names = {
            'INPUT_RATING': 'input_rating',
            'INPUT_NUMBER': 'input_number',
            'INPUT_SHORT_TEXT': 'input_short_text',
            'INPUT_LONG_TEXT': 'input_long_text',
            'INPUT_LINK': 'input_link',
            'INPUT_EMAIL': 'input_email',
            'INPUT_DATE': 'input_date',
            'INPUT_MULTIPLE_CHOICE': 'input_multiple_choice',
            'INPUT_DROPDOWN': 'input_dropdown',
            'INPUT_CHECKBOXES': 'input_checkboxes',
            'INPUT_PHONE_NUMBER': 'input_phone_number',
            'INPUT_RANKING': 'input_ranking',
            'INPUT_FILE_UPLOAD': 'input_file_upload'
        }

        input_field_type = input_field.get('type', '')
        answer_choice_values = field_answer.get('choices', {}).get('values', []) if field_answer.get('choices',
                                                                                                     {}) else []
        file_metadata_name = field_answer.get("file_metadata", {}).get('name', '') if field_answer.get("file_metadata",
                                                                                                       {}) else ""

        if input_field_type in [form_builder_tag_names['INPUT_RATING'], form_builder_tag_names['INPUT_NUMBER']]:
            return field_answer.get('number', '')
        elif input_field_type in [form_builder_tag_names['INPUT_SHORT_TEXT'],
                                  form_builder_tag_names['INPUT_LONG_TEXT']]:
            return field_answer.get('text', '')
        elif input_field_type == form_builder_tag_names['INPUT_LINK']:
            return field_answer.get('url', '')
        elif input_field_type == form_builder_tag_names['INPUT_EMAIL']:
            return field_answer.get('email', '')
        elif input_field_type == form_builder_tag_names['INPUT_DATE']:
            return field_answer.get('date', '')
        elif input_field_type in [form_builder_tag_names['INPUT_MULTIPLE_CHOICE'],
                                  form_builder_tag_names['INPUT_DROPDOWN']]:
            return next((choice['value'] for choice in input_field.get('properties', {}).get('choices', []) if
                         choice['id'] == field_answer.get('choice', {}).get('value')), '')
        elif input_field_type == form_builder_tag_names['INPUT_CHECKBOXES']:
            choices = [choice['value'] for choice in input_field.get('properties', {}).get('choices', []) if
                       choice['id'] in answer_choice_values]
            return ', '.join(choices)
        elif input_field_type == form_builder_tag_names['INPUT_PHONE_NUMBER']:
            return field_answer.get('phone_number', '')
        elif input_field_type == form_builder_tag_names['INPUT_RANKING']:
            return ', '.join(choice.get('value', '') for choice in answer_choice_values)
        elif input_field_type == form_builder_tag_names['INPUT_FILE_UPLOAD']:
            return file_metadata_name
        else:
            return ''

    def get_simple_form_response():
        simple_form = {
            **form
        }
        for field in simple_form.get("fields"):
            if field.get("type") and "input_" in str(field.get("type")):
                answers = response.get("answers")
                if answers is not None:
                    answer_for_field = answers.get(str(field.get("id")))
                    field["answer"] = get_answer_for_field(answer_for_field,
                                                           field) if answer_for_field else "&nbsp;"
        return simple_form

    def send_mail_action(config, subject, recipient: List[str], creator_mail: Optional[bool] = False):
        mail_config = config

        message = MessageSchema(
            subject=subject,
            recipients=recipient,
            subtype=MessageType.html,
            template_body={"form": get_simple_form_response(), "response": response, "creator_mail": creator_mail},
        )
        fast_mail = FastMail(mail_config)
        asyncio.run(fast_mail.send_message(message, template_name="response-mail.html"))
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
                                                         send_mail_action,
                                                         get_simple_form_response,
                                                         get_workspace_details
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
                        send_mail_action,
                        get_simple_form_response,
                        get_workspace_details):
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
                "get_workspace_details": get_workspace_details
            }, {}
        )
    except Exception as e:
        log("Exception While running action")
        log(str(e))
        traceback.print_exception(e)
        raise RuntimeError("\n".join(log_string))
    return {
        "status": status,
        "log": "\n".join(log_string)
    }

import asyncio
import json
import re
import traceback
from http import HTTPStatus
from random import Random
from typing import Any, Dict, List, Optional

import httpx
from fastapi_mail import ConnectionConfig, MessageSchema, FastMail, MessageType
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from pydantic import EmailStr

from configs.crypto import crypto
from models.date import GOOGLE_DATETIME_FORMAT
from models.exception_enum import ExceptionType
from settings.application import settings
from utilities.exceptions import HTTPException
from wrappers.thread_pool_executor import thread_pool_executor

from googleapiclient.discovery import build
import google.oauth2.credentials
from datetime import datetime


async def run_action(
        action: Any,
        form: Any,
        response: Any,
        user_email: Optional[EmailStr] = None,
        workspace: Optional[str] = None
):
    workspace = json.loads(workspace)
    action = json.loads(action)
    form = json.loads(form)
    response = json.loads(response)

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

        # process workspace data
        a = workspace
        workspace_data = workspace.get(key, {})
        if workspace_data is not None:
            overriding_data = workspace_data.get(action.get("id"), [])
            for overriding_item in overriding_data:
                name, value = process_item(overriding_item, key == "secrets")
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

    def get_responses_in_array():
        simple_form = {
            **form
        }
        # this is for integrate-google-sheet and here response might be multiple
        responses = []
        form_response_array = []
        for field in simple_form.get("fields"):
            if field.get("type") and "input_" in str(field.get("type")):
                answers = response.get("answers")
                if answers is not None:
                    answer_for_field = answers.get(str(field.get("id")))
                    form_response_array.append(get_answer_for_field(answer_for_field,
                                                                    field) if answer_for_field else "&nbsp;")
        return form_response_array

    def get_form_question_in_array():
        simple_form = {
            **form
        }
        fields = simple_form.get("fields")
        question_list = []
        for field in fields:
            if field.get("type") and "input_" in str(field.get("type")):
                question_field = get_previous_field(field.get("id"), fields)
                if question_field:
                    question_value = question_field.get("value", "")
                    if '{{' in question_value:
                        question_value = get_question_value(question_value, fields)[:40]
                    question_list.append(question_value)
        return question_list

    def get_question_value(question_value, fields):
        pattern = r"\b[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}\b"
        ids = re.findall(pattern, question_value)
        for field_id in ids:
            previous_field_value = get_previous_field(field_id, fields)['value']
            if '{{' in previous_field_value:
                previous_field_value = get_question_value(previous_field_value, fields)
            question_value = question_value.replace('{{ ', '@').replace('}}', '').replace(field_id,
                                                                                          previous_field_value)
        return question_value

    def get_previous_field(field_id, fields):
        for index, field in enumerate(fields):
            if field['id'] == field_id:
                return fields[index - 1] if fields[index - 1] else None

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

    def build_google_service(credentials, service_name: str, version: str = "v1"):
        return build(
            serviceName=service_name,
            version=version,
            credentials=dict_to_credential(credentials),
        )

    def dict_to_credential(credentials_dict):
        credentials = google.oauth2.credentials.Credentials(**credentials_dict)
        expiry = credentials.expiry
        if isinstance(expiry, datetime):
            expiry = expiry.strftime(GOOGLE_DATETIME_FORMAT)
        credentials.expiry = datetime.strptime(expiry, GOOGLE_DATETIME_FORMAT)
        return credentials

    def create_sheet(credentials):
        credentials = json.loads(credentials).get("credentials")
        credentials['scopes'] = credentials.get('scopes').split(' ')[1:]
        spreadsheet = {"properties": {"title": "Another GoogleSheet"}}
        google_sheet = (
            build_google_service(credentials=credentials, service_name="sheets", version="v4")
            .spreadsheets()
            .create(body=spreadsheet, fields="spreadsheetId")
            .execute()
        )
        return google_sheet.get("spreadsheetId")

    def append_in_sheet(google_sheet_id, credentials, question_array, response_array):
        question = {"values": [question_array]}
        response_body = {"values": [response_array]}
        credentials = json.loads(credentials).get("credentials")
        credentials['scopes'] = credentials.get('scopes').split(' ')[1:]
        try:
            google_sheet_question = (
                build_google_service(credentials=credentials, service_name="sheets", version="v4")
                .spreadsheets().values()
                .update(spreadsheetId=google_sheet_id,
                        range=f"A1:{chr(ord('A') + len(question_array))}1",
                        valueInputOption="USER_ENTERED",
                        body=question)
                .execute()
            )
            google_sheet_response = (
                build_google_service(credentials=credentials, service_name="sheets", version="v4")
                .spreadsheets().values()
                .append(spreadsheetId=google_sheet_id,
                        range="Sheet1",
                        valueInputOption="USER_ENTERED",
                        body=response_body)
                .execute()
            )
            return "Appended"
        except HttpError:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=ExceptionType.GOOGLE_SHEET_MISSING)
        except RefreshError as e:
            raise HTTPException(status_code=HTTPStatus.EXPECTATION_FAILED, content=ExceptionType.OAUTH_TOKEN_MISSING)

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
                                                         action,
                                                         workspace,
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
                                                         get_form_question_in_array,
                                                         get_responses_in_array,
                                                         create_sheet,
                                                         build_google_service,
                                                         dict_to_credential,
                                                         append_in_sheet
                                                         ), timeout=30)
    return result


def execute_action_code(action_code: str,
                        response,
                        form,
                        action,
                        workspace,
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
                        get_form_question_in_array,
                        get_responses_in_array,
                        create_sheet,
                        build_google_service,
                        dict_to_credential,
                        append_in_sheet
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
                "print": print,
                "type": type,
                "HTTPException": HTTPException,
                "json": json,
                "log": log,
                "random": Random,
                "action_code": action_code,
                "response": response,
                "form": form,
                "action": action,
                "workspace": workspace,
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
                "get_form_question_in_array": get_form_question_in_array,
                "get_responses_in_array": get_responses_in_array,
                "create_sheet": create_sheet,
                "build_google_service": build_google_service,
                "dict_to_credential": dict_to_credential,
                "append_in_sheet": append_in_sheet
            }, {}
        )
    except (HTTPException, Exception) as e:
        log("Exception While running action")
        log(str(e))
        if str(e) == ExceptionType.GOOGLE_SHEET_MISSING or str(e) == ExceptionType.OAUTH_TOKEN_MISSING:
            httpx.patch(
                url=f"{settings.server_url}/workspaces/{workspace.get('id')}/forms/{form.get('form_id')}/action/{action.get('id')}/update",
            )
        traceback.print_exception(e)
        raise RuntimeError("\n".join(log_string))
    return {
        "status": status,
        "log": "\n".join(log_string)
    }

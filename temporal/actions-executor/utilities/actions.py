import asyncio
import json
import os
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
from models.exception_enum import ExceptionType
from settings.application import settings
from utilities.exceptions import HTTPException
from utilities.google_service import build_google_service, fetch_oauth_token
from wrappers.thread_pool_executor import thread_pool_executor
from utilities.form import get_questions_and_answers
from settings.application import settings


async def run_action(
    action: Any,
    form: Any,
    response: Any,
    user_email: Optional[EmailStr] = None,
    workspace: Optional[str] = None,
):
    workspace = json.loads(workspace)
    action = json.loads(action)
    form = json.loads(form)
    response = json.loads(response)

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
            if item_name is not None and item_value is not None and item_value != "":
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

        # process workspace data
        workspace_data = workspace.get(key, {})
        if workspace_data is not None:
            overriding_data = workspace_data.get(action.get("id"), [])
            overriding_data = [] if overriding_data is None else overriding_data

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
                "title": form.get("welcome_page", {}).get("title", "Untitled Form"),
                "description": form.get("welcome_page", {}).get("description", ""),
            },
        )
        fast_mail = FastMail(mail_config)
        asyncio.ensure_future(
            fast_mail.send_message(message, template_name="response-mail.html")
        )
        return "ok"

    def append_in_sheet(
        google_sheet_id: str = None, credentials: str = None, data=None
    ):
        credentials = json.loads(credentials)
        credential = fetch_oauth_token(
            oauth_credential=credentials,
            action_id=action["id"],
            form_id=form["form_id"],
        )
        credential["scopes"] = credential.get("scopes").split(" ")[1:]

        # Extract questions and answers from the response
        question_array = [qa["title"] for qa in data]
        response_array = [qa["answer"] for qa in data]

        # Prepare the data to append (first row: questions, second row: responses)
        question_data = {"values": [question_array]}
        response_data = {"values": [response_array]}

        try:
            # Build the Sheets service
            service = build_google_service(
                credentials=credential, service_name="sheets", version="v4"
            )

            # Check if the sheet already has questions in row 1
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=google_sheet_id, range="A1:1")
                .execute()
            )
            existing_questions = result.get("values", [[]])[0]
            new_questions = []
            updated_questions = False

            for i, question in enumerate(question_array):
                if i < len(existing_questions):
                    if existing_questions[i] != question:
                        existing_questions[i] = question  # Update modified question
                        updated_questions = True
                else:
                    existing_questions.append(question)  # Append new questions
                    updated_questions = True

            if updated_questions:  # If no questions exist, insert them
                # Update the first row (questions)
                service.spreadsheets().values().update(
                    spreadsheetId=google_sheet_id,
                    range=f"A1:{chr(ord('A') + len(existing_questions)-1)}1",
                    valueInputOption="USER_ENTERED",
                    body={"values": [existing_questions]},
                ).execute()

                # Apply formatting (bold and underline) to the first row
                requests = [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": 0,  # Assuming the first sheet, otherwise fetch the correct sheetId
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": len(question_array),
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True, "underline": True},
                                    "backgroundColor": {
                                        "red": 0.9,
                                        "green": 0.9,
                                        "blue": 0.9,
                                    },
                                }
                            },
                            "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor",
                        }
                    }
                ]

                # Send batchUpdate request to format the first row
                service.spreadsheets().batchUpdate(
                    spreadsheetId=google_sheet_id, body={"requests": requests}
                ).execute()

            # Append the responses to the sheet
            append_response = (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=google_sheet_id,
                    range="A2",  # Starting at A2, will auto-increment
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",  # Ensures new rows are inserted
                    body=response_data,
                )
                .execute()
            )

            # Apply formatting to the last appended row (responses)
            row_index = (
                append_response["updates"]["updatedRange"]
                .split("!")[-1]
                .split(":")[0][1:]
            )  # Get the starting row of the appended data
            row_index = int(row_index) - 1  # Convert to 0-based index

            # Apply color formatting for the response row
            response_formatting_request = [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,  # Assuming first sheet
                            "startRowIndex": row_index,
                            "endRowIndex": row_index + 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(response_array),
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": False, "underline": False},
                                "backgroundColor": {
                                    "red": 0.8,
                                    "green": 0.9,
                                    "blue": 1,
                                },
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            ]

            # Send batchUpdate request to format the last row (response)
            service.spreadsheets().batchUpdate(
                spreadsheetId=google_sheet_id,
                body={"requests": response_formatting_request},
            ).execute()
            return "Appended"

        except HttpError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content=ExceptionType.GOOGLE_SHEET_MISSING,
                )
        except RefreshError as e:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=ExceptionType.OAUTH_TOKEN_MISSING,
            )

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

    def send_data_discord(url: str, params=None, data=None, headers=None):
        if data is None:
            data = {}

        fields = []
        for q_n_a in data:
            fields.append(
                {
                    "name": q_n_a["title"],
                    "value": q_n_a["answer"],
                    "inline": False,
                }
            )
        payload = {
            "content": f"🎉 **Congratulations!** You received a new response on! **{form['title']}**",
            "embeds": [
                {
                    "color": 0x00FF00,
                    "description": f"[View Form response here]({settings.frontend_url}/{workspace['workspace_name']}/dashboard/forms/{form['form_id']}/?view=Responses)\n --------------------------",
                    "fields": fields,
                    "footer": {"text": "Thank You for using Bettercollected"},
                }
            ],
        }
        res = httpx.post(url=url, params=params, json=payload, headers=headers)
        return res

    def send_data_slack(url: str, params=None, data=None, headers=None):
        if data is None:
            data = {}

        fields = []
        for q_n_a in data:
            fields.append(
                {
                    "title": q_n_a["title"],
                    "value": q_n_a["answer"],
                    "short": False,
                }
            )

        payload = {
            "attachments": [
                {
                    "title": f"🎉 **Congratulations!** You received a new response on! `{form['title']}`\n\n",
                    "color": "#00FF00",
                    "text": (
                        f"Click <{settings.frontend_url}/{workspace['workspace_name']}/dashboard/forms/{form['form_id']}/?view=Responses|here> to view the form response.\n\n"
                        "Details:\n"
                    ),
                    "fields": fields,
                    "footer": "Thank you for using Bettercollected",
                }
            ]
        }
        res = httpx.post(url=url, params=params, json=payload, headers=headers)
        return res

    def send_message_to_discord():
        URL = get_parameter("Discord Webhook URL")
        data = get_simple_form_response()
        send_data_discord(URL, data=data)

    def send_message_to_slack():
        URL = get_parameter("Slack Webhook URL")
        data = get_simple_form_response()
        send_data_slack(URL, data=data)

    def integrate_google_sheets_append_action():
        Google_sheet_id = get_parameter("Google Sheet Id")
        credentials = get_secret("Credentials")
        data = get_simple_form_response()
        append_in_sheet(Google_sheet_id, credentials, data)

    if action.get("predefined"):
        match action.get("name"):
            case "send_webhook":
                return send_webhook_action()
            case "responder_copy_mail":
                return send_responder_a_copy_of_mail()
            case "creator_copy_mail":
                return send_me_a_copy_of_response()
            case "send_to_discord":
                return send_message_to_discord()
            case "send_to_slack":
                return send_message_to_slack()
            case "integrate_google_sheets":
                return integrate_google_sheets_append_action()
        return
    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(
            thread_pool_executor,
            execute_action_code,
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
            send_data_discord,
            send_data_slack,
            config_mail,
            send_mail_action,
            get_simple_form_response,
            get_workspace_details,
            get_form_question_in_array,
            get_responses_in_array,
            append_in_sheet,
        ),
        timeout=30,
    )
    return result


def execute_action_code(
    action_code: str,
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
    send_data_discord,
    send_data_slack,
    config_mail,
    send_mail_action,
    get_simple_form_response,
    get_workspace_details,
    get_form_question_in_array,
    get_responses_in_array,
    append_in_sheet,
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
                "send_data_discord": send_data_discord,
                "send_data_slack": send_data_slack,
                "config_mail": config_mail,
                "send_mail_action": send_mail_action,
                "get_simple_form_response": get_simple_form_response,
                "get_workspace_details": get_workspace_details,
                "get_form_question_in_array": get_form_question_in_array,
                "get_responses_in_array": get_responses_in_array,
                "append_in_sheet": append_in_sheet,
                "fetch_oauth_token": fetch_oauth_token,
                "build_google_service": build_google_service,
            },
            {},
        )
    except (HTTPException, Exception) as e:
        log("Exception While running action")
        log(str(e))
        if (
            str(e) == ExceptionType.GOOGLE_SHEET_MISSING
            or str(e) == ExceptionType.OAUTH_TOKEN_MISSING
        ):
            httpx.patch(
                url=f"{settings.server_url}/workspaces/{workspace.get('id')}/forms/{form.get('form_id')}/action/{action.get('id')}/update",
                headers={"api-key": settings.api_key},
            )
        traceback.print_exception(e)
        raise RuntimeError("\n".join(log_string))
    return {"status": status, "log": "\n".join(log_string)}

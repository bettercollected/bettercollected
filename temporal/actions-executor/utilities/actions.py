import asyncio
import json
import logging
import os
from http import HTTPStatus
from random import Random
from typing import Any, Dict, List, Optional

import httpx
from fastapi_mail import ConnectionConfig, MessageSchema, MessageType
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from pydantic import EmailStr

from configs.cipher import crypto
from models.exception_enum import ExceptionType
from settings.application import isolation_enforced, settings
from utilities import egress
from utilities.custom_action import Toolbox, run_custom_code
from utilities.pinned_mail import PinnedFastMail as FastMail
from utilities.exceptions import HTTPException
from utilities.google_service import (
    RunScope,
    build_google_service,
    fetch_oauth_token,
    writeback_for,
)
from wrappers.thread_pool_executor import thread_pool_executor
from utilities.form import (
    column_letter,
    formula_safe,
    get_group_tables,
    get_questions_and_answers,
    sheet_title_for,
)
from utilities.copy_recipient import approved_copy_recipient
from utilities.mail import response_mail_context
from utilities.smtp_group import merge_layers, smtp_overridden, smtp_settings
from utilities.mail_headers import (
    FROM_NAME_MAX,
    SUBJECT_MAX,
    one_line,
    respondent_from_name,
)
from settings.application import settings

logger = logging.getLogger(__name__)


async def run_action(
    action: Any,
    form: Any,
    response: Any,
    user_email: Optional[EmailStr] = None,
    workspace: Optional[str] = None,
    secrets_plain: bool = False,
    run_scope: Optional[RunScope] = None,
):
    """Run one action. ``secrets_plain``: the backend already opened the run's
    secrets (the executor then holds no key); otherwise they are sealed and are
    opened with this process's key, as 4.2 did. ``run_scope``: the ids and token
    of the run, used to hand a refreshed credential back to the backend."""
    workspace = json.loads(workspace)
    action = json.loads(action)
    form = json.loads(form)
    response = json.loads(response)

    if form.get("builder_version") != "v2":
        return

    if not isolation_enforced():
        logger.warning(
            "ACTION_ISOLATION=legacy: action %s runs without isolation "
            "(custom code in this process, no egress rules)",
            action.get("id"),
        )

    def get_state():
        if response.state and response.state.global_state:
            return response.state.global_state
        return None

    def get_workspace_details():
        return workspace

    def process_item(variable, decrypt=False):
        item_name = variable.get("name")
        item_value = variable.get("value")
        if item_name is not None and item_value is not None and item_value != "":
            return item_name, (
                item_value if not decrypt else crypto.decrypt(item_value)
            )
        return None, None

    def collect(items, decrypt) -> Dict[str, str]:
        values = {}
        for item in items or []:
            name, value = process_item(item, decrypt)
            if name is not None:
                values[name] = value
        return values

    def get_extra_data(key: str) -> Dict[str, str]:
        # a secret is opened here unless the backend already opened it
        decrypt = key == "secrets" and not secrets_plain
        action_id = action.get("id")

        # the action's own values (the instance's defaults)
        action_values = collect(action.get(key, []), decrypt)

        # the workspace's overrides
        workspace_data = workspace.get(key, {})
        workspace_values = collect(
            (workspace_data or {}).get(action_id, []) if workspace_data else [],
            decrypt,
        )

        # the form's overrides
        form_data = form.get(key, {})
        form_values = collect(
            (form_data or {}).get(action_id, []) if form_data else [], decrypt
        )

        # the SMTP settings come from one side only, never name by name
        return merge_layers(
            action_values,
            workspace_values,
            form_values,
            smtp_overridden(action, workspace, form),
        )

    # What the administrators who created the action configured (its own
    # parameters; its secrets too when they arrive opened): their addresses are
    # trusted destinations, a workspace's or a form's are not (utilities/egress.py)
    smtp_trusted = not smtp_overridden(action, workspace, form)
    trusted_origins = egress.trusted_origins_of(
        [
            *collect(action.get("parameters", []), False).values(),
            *(
                collect(action.get("secrets", []), False).values()
                if secrets_plain
                else []
            ),
        ]
    )

    def names_of(items):
        return {
            item.get("name")
            for item in items or []
            if item.get("name") is not None and item.get("value") not in (None, "")
        }

    # secrets stored on the action itself and not overridden by the workspace or
    # the form: the administrators', which only go to the addresses they set
    _action_id = action.get("id")
    instance_secrets = names_of(action.get("secrets", [])) - (
        names_of(((workspace.get("secrets") or {}).get(_action_id)))
        | names_of(((form.get("secrets") or {}).get(_action_id)))
    )
    egress_allow = egress.parse_allow(settings.action_egress_allow)
    # a refreshed Google credential goes back to the backend as plain text for it
    # to seal, when the secrets came opened (this process holds no key then)
    writeback = writeback_for(run_scope) if (secrets_plain and run_scope) else None

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
            # one line, capped: a title can never add a header
            MAIL_FROM_NAME=one_line(org_name, FROM_NAME_MAX),
            MAIL_STARTTLS=tls,
            MAIL_SSL_TLS=ssl,
            USE_CREDENTIALS=use_credentials,
            VALIDATE_CERTS=validate_certs,
            TEMPLATE_FOLDER="templates",
        )

    def check_smtp_destination(server, port):
        """A mail server a workspace or a form named must be a public one; the
        instance's own (the action's defaults) is not judged."""
        if isolation_enforced():
            egress.check_smtp(server, port, allow=egress_allow, trusted=smtp_trusted)

    def get_simple_form_response(respondent: bool = False):
        # a copy the respondent receives leaves out calculations kept from them
        extracted_question_answers = get_questions_and_answers(
            form=form, response=response, respondent=respondent
        )
        return extracted_question_answers

    def build_mail(subject, recipient: List[str], creator_mail):
        return MessageSchema(
            subject=one_line(subject, SUBJECT_MAX),
            recipients=recipient,
            subtype=MessageType.html,
            template_body=response_mail_context(
                fields=get_simple_form_response(respondent=not creator_mail),
                creator_mail=creator_mail,
                title=form.get("welcome_page", {}).get("title", "Untitled Form"),
                description=form.get("welcome_page", {}).get("description", ""),
            ),
        )

    def mailer(mail_config):
        fast_mail = FastMail(mail_config)
        pin = getattr(fast_mail, "pin", None)
        if pin is not None:
            # connect to the address the egress rules checked (utilities/pinned_mail.py)
            pin(allow=egress_allow, trusted=smtp_trusted or not isolation_enforced())
        return fast_mail

    async def deliver_mail(
        mail_config, subject, recipient: List[str], creator_mail: bool = False
    ):
        """Send one mail and wait for the server: a failure is the run's failure."""
        await mailer(mail_config).send_message(
            build_mail(subject, recipient, creator_mail),
            template_name="response-mail.html",
        )
        return "ok"

    def send_mail_action(
        config, subject, recipient: List[str], creator_mail: Optional[bool] = False
    ):
        """The in-process (legacy) code's mail: sent in the background."""
        asyncio.ensure_future(deliver_mail(config, subject, recipient, creator_mail))
        return "ok"

    def prepare_mail(respondent: bool):
        """The action's SMTP group, checked, as a mail configuration (blocking:
        the destination's name is resolved). ``respondent``: the copy a
        respondent gets, sent as "<workspace> via <instance>"."""
        username, password, sender, port, server = smtp_settings(
            get_parameters(), get_secrets()
        )
        check_smtp_destination(server, port)
        from_name = (
            respondent_from_name(
                get_workspace_details().get("title"), settings.organization_name
            )
            if respondent
            else ""
        )
        if respondent:
            return config_mail(username, password, sender, port, server, from_name)
        return config_mail(username, password, sender, port, server)

    async def blocking(function, *args):
        """A blocking step (a name lookup, a call to the backend, a slow
        destination) off the event loop."""
        return await asyncio.get_running_loop().run_in_executor(
            thread_pool_executor, function, *args
        )

    def append_in_sheet(
        google_sheet_id: str = None, credentials: str = None, data=None
    ):
        credentials = json.loads(credentials)
        credential = fetch_oauth_token(
            oauth_credential=credentials,
            action_id=action["id"],
            form_id=form["form_id"],
            writeback=writeback,
        )
        credential["scopes"] = credential.get("scopes").split(" ")[1:]

        # Extract questions and answers from the response
        # USER_ENTERED runs cells starting with = + - @ as formulas: never
        # let a title or a respondent's answer become one.
        question_array = [formula_safe(qa["title"]) for qa in data]
        response_array = [formula_safe(qa["answer"]) for qa in data]

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
                    range=f"A1:{column_letter(len(existing_questions))}1",
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

        if isolation_enforced():
            # the address was typed by a form creator: public https only, the
            # checked address is the one connected to (utilities/egress.py)
            if headers["Content-Type"] == "application/json":
                return egress.post(
                    url,
                    params=params,
                    json_body=data,
                    headers=headers,
                    allow=egress_allow,
                    trusted=trusted_origins,
                )
            return egress.post(
                url,
                params=params,
                form=data,
                headers=headers,
                allow=egress_allow,
                trusted=trusted_origins,
            )
        if headers["Content-Type"] == "application/json":
            res = httpx.post(
                url=url, params=params, content=json.dumps(data), headers=headers
            )
        else:
            res = httpx.post(url=url, params=params, data=data, headers=headers)
        return res

    async def send_webhook_action():
        URL = get_parameter("Webhook URL")
        data = get_simple_form_response()
        await blocking(lambda: send_data_webhook(URL, data=data))

    async def send_responder_a_copy_of_mail():
        form = get_form()
        response = get_response()

        if response.get("dataOwnerIdentifier"):
            mail_config = await blocking(prepare_mail, True)
            await deliver_mail(
                mail_config,
                "Copy of your response to " + form.get("title", "Untitled Form"),
                [response.get("dataOwnerIdentifier")],
            )

    async def send_me_a_copy_of_response():
        form = get_form()

        receiving_mail = get_parameter("Receiving Mail Address")

        if receiving_mail:
            # Only a current member of the workspace (the creator while one):
            # checked now, not as of when the action was saved (a refusal or a
            # failed check raises, so nothing is sent and the job shows why)
            receiving_mail = await blocking(
                approved_copy_recipient,
                receiving_mail,
                get_workspace_details().get("id"),
                form.get("form_id"),
                action.get("id"),
            )
            mail_config = await blocking(prepare_mail, False)
            await deliver_mail(
                mail_config,
                "You have got a new response in " + form.get("title", "Untitled Form"),
                [receiving_mail],
                True,
            )

    def send_data_discord(url: str, params=None, data=None, headers=None):
        """
        Send form response to Discord webhook with proper field sanitization.
        Handles null/empty answers and prevents 400 errors from invalid embeds.
        """
        if data is None:
            data = {}

        fields = []
        for q_n_a in data:
            # Safely get title and answer with defaults
            title = str(q_n_a.get("title", "Question")).strip()
            answer = q_n_a.get("answer")

            # Force value to be a non-empty string (Discord requirement)
            if answer is None or answer == "":
                value = "—"
            else:
                value = str(answer).strip()

            # Truncate to Discord limits
            title = title[:256] if title else "Untitled"
            value = value[:1024] if value else "—"

            # Optional: skip completely empty optional-looking fields
            # if value == "—" and "(optional)" in title.lower():
            #     continue

            fields.append(
                {
                    "name": title,
                    "value": value,
                    "inline": False,
                }
            )

        # Respect Discord embed field limit
        if len(fields) > 25:
            fields = fields[:25]

        # Build payload
        payload = {
            "content": f"🎉 **Congratulations!** You received a new response on **{form['title']}**",
            "embeds": [
                {
                    "color": 0x00FF00,  # Green - correct integer format
                    "description": (
                        f"[View Form response here]({settings.frontend_url}/"
                        f"{workspace['workspace_name']}/dashboard/forms/"
                        f"{form['form_id']}/?view=Responses)\n"
                        "--------------------------"
                    ),
                    "fields": fields,
                    "footer": {"text": "Thank You for using Bettercollected"},
                    # Optional: add timestamp if you want
                    # "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }

        # Optional: add better error logging in development
        if isolation_enforced():
            return egress.post(
                url,
                params=params,
                json_body=payload,
                headers=headers,
                allow=egress_allow,
                trusted=trusted_origins,
            )
        try:
            res = httpx.post(
                url=url, params=params, json=payload, headers=headers, timeout=10.0
            )
            return res
        except httpx.RequestError as e:
            print(f"Discord request error: {e}")
            # Return fake response or raise — your choice
            from httpx import Response

            return Response(status_code=503, request=None)

    def send_data_slack(url: str, params=None, data=None, headers=None):
        if data is None:
            data = {}

        fields = []
        for q_n_a in data:
            fields.append(
                {
                    "title": q_n_a["title"],
                    "value": q_n_a["answer"] if q_n_a["answer"] else "—",
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
        if isolation_enforced():
            return egress.post(
                url,
                params=params,
                json_body=payload,
                headers=headers,
                allow=egress_allow,
                trusted=trusted_origins,
            )
        res = httpx.post(url=url, params=params, json=payload, headers=headers)
        return res

    async def send_message_to_discord():
        URL = get_parameter("Discord Webhook URL")
        data = get_simple_form_response()
        await blocking(lambda: send_data_discord(URL, data=data))

    async def send_message_to_slack():
        URL = get_parameter("Slack Webhook URL")
        data = get_simple_form_response()
        await blocking(lambda: send_data_slack(URL, data=data))

    def append_group_tables_in_sheet(google_sheet_id: str, credentials: str, tables):
        """Rows-layout repeating groups: one tab per group, one row per item."""
        if not tables:
            return "Nothing to append"
        credential = fetch_oauth_token(
            oauth_credential=json.loads(credentials),
            action_id=action["id"],
            form_id=form["form_id"],
            writeback=writeback,
        )
        credential["scopes"] = credential.get("scopes").split(" ")[1:]
        try:
            service = build_google_service(
                credentials=credential, service_name="sheets", version="v4"
            )
            spreadsheet = (
                service.spreadsheets()
                .get(spreadsheetId=google_sheet_id, fields="sheets.properties.title")
                .execute()
            )
            existing = {
                sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])
            }
            for table in tables:
                title = table.get("sheet_title") or sheet_title_for(table["title"])
                if title not in existing:
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=google_sheet_id,
                        body={
                            "requests": [{"addSheet": {"properties": {"title": title}}}]
                        },
                    ).execute()
                    existing.add(title)
                service.spreadsheets().values().update(
                    spreadsheetId=google_sheet_id,
                    range=f"'{title}'!A1:{column_letter(len(table['headers']))}1",
                    valueInputOption="USER_ENTERED",
                    body={"values": [[formula_safe(v) for v in table["headers"]]]},
                ).execute()
                if table["rows"]:
                    service.spreadsheets().values().append(
                        spreadsheetId=google_sheet_id,
                        range=f"'{title}'!A2",
                        valueInputOption="USER_ENTERED",
                        insertDataOption="INSERT_ROWS",
                        body={
                            "values": [
                                [formula_safe(v) for v in row] for row in table["rows"]
                            ]
                        },
                    ).execute()
            return "Appended"
        except HttpError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content=ExceptionType.GOOGLE_SHEET_MISSING,
                )
            raise
        except RefreshError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=ExceptionType.OAUTH_TOKEN_MISSING,
            )

    def integrate_google_sheets_append_action():
        Google_sheet_id = get_parameter("Google Sheet Id")
        credentials = get_secret("Credentials")
        # Fixed columns: a repeating group's columns do not depend on how many
        # items this response has, so rows of different responses line up.
        data = get_questions_and_answers(
            form=form, response=response, fixed_columns=True
        )
        append_in_sheet(Google_sheet_id, credentials, data)
        append_group_tables_in_sheet(
            Google_sheet_id, credentials, get_group_tables(form=form, response=response)
        )

    if action.get("predefined"):
        match action.get("name"):
            case "send_webhook":
                return await send_webhook_action()
            case "responder_copy_mail":
                return await send_responder_a_copy_of_mail()
            case "creator_copy_mail":
                return await send_me_a_copy_of_response()
            case "send_to_discord":
                return await send_message_to_discord()
            case "send_to_slack":
                return await send_message_to_slack()
            case "integrate_google_sheets":
                return await blocking(integrate_google_sheets_append_action)
        return
    if isolation_enforced():
        return await run_isolated_code(
            action_id=action.get("id"),
            action_code=action.get("action_code"),
            data={
                "action": action,
                "form": form,
                "response": response,
                "workspace": workspace,
                "simple_response": get_simple_form_response(),
            },
            toolbox=Toolbox(
                parameters=get_parameters(),
                secrets=get_secrets(),
                trusted_origins=trusted_origins,
                instance_secrets=instance_secrets,
                respondent_email=response.get("dataOwnerIdentifier"),
                webhook=send_data_webhook,
                discord=send_data_discord,
                slack=send_data_slack,
                prepare_mail=prepare_mail,
                deliver_mail=deliver_mail,
                append_sheet=lambda sheet_id, credentials, rows: append_in_sheet(
                    sheet_id, credentials, rows
                ),
                approved_recipient=lambda address: approved_copy_recipient(
                    address,
                    workspace.get("id"),
                    form.get("form_id"),
                    action.get("id"),
                ),
                mark_broken=lambda: mark_action_broken(workspace, form, action),
                allow=egress_allow,
            ),
        )
    # ACTION_ISOLATION=legacy: the code runs in this process, which it can reach
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
            append_in_sheet,
        ),
        timeout=30,
    )
    return result


def mark_action_broken(workspace, form, action) -> None:
    """The action's stored sheet or credential is gone: tell the backend, which
    switches the action off."""
    httpx.patch(
        url=f"{settings.server_url}/workspaces/{workspace.get('id')}/forms/{form.get('form_id')}/action/{action.get('id')}/update",
        headers={"api-key": settings.api_key},
    )


async def run_isolated_code(*, action_code, data, toolbox, action_id):
    """Custom action code in the sandbox (sandbox/, utilities/custom_action.py).
    The result and the failure look as the in-process run's did: the code's log,
    or a RuntimeError holding the log; the class of an error, never a traceback.
    What the code says never switches an action off (only the executor's own
    Google call does, in ``custom_action.py``)."""
    outcome = await run_custom_code(action_code, data=data, toolbox=toolbox)
    log_lines = list(outcome.log)
    error = outcome.error
    if error is None:
        return {"status": True, "log": "\n".join(log_lines)}
    log_lines.append("Exception While running action")
    log_lines.append(str(error.get("message") or ""))
    logger.error(
        "action %s failed in its code: %s",
        action_id,
        error.get("class") or error.get("kind"),
    )
    raise RuntimeError("\n".join(log_lines))


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
        # the class of the error, not its message or traceback: an exception
        # raised by a creator's code or a provider can carry an answer
        logger.error(
            "action %s failed in its code: %s", action.get("id"), type(e).__name__
        )
        raise RuntimeError("\n".join(log_string))
    return {"status": status, "log": "\n".join(log_string)}

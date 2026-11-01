"""Custom action code, run in the sandbox (``sandbox/``), and the calls it may make.

The code gets this run's data (the form, the response, the workspace, the merged
parameters, **the names of the secrets and none of their values**) and the
calls below. Each call is checked here, in the executor, which holds the
secrets and does the work; the sandbox holds nothing and can reach nothing:

- ``send_data_webhook`` / ``send_data_discord`` / ``send_data_slack``: only to
  an address this run is configured with (a parameter or secret of the action,
  the workspace or the form, or an operator-allowed host), and then through the
  egress rules (public https, the address checked, no redirects);
- ``send_mail_action``: the SMTP settings must be the configured ones (a value
  of this run's parameters or secrets), the server is checked like any other
  destination, and the recipients are the respondent or a current member of the
  workspace, at most five;
- ``append_in_sheet``: the sheet is one this run is configured with and the
  credential is the run's own stored credential;
- a secret is passed by name (a handle the code cannot read) in headers, a body
  or a mail login, and replaced by its value here.

The number of calls, their size, the time and the memory are limited.
"""

import asyncio
import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from sandbox import broker
from sandbox.broker import CallRefused, Outcome
from settings.application import settings
from utilities import egress
from utilities.exceptions import HTTPException as ActionHTTPException

logger = logging.getLogger(__name__)

SECRET_KEY = "$secret"
MAX_RECIPIENTS = 5
MAX_SUBJECT = 300
MAX_SHEET_ROWS = 500
REPLY_TEXT_MAX = 4096
MAIL_KEYS = (
    "smtp_username",
    "smtp_password",
    "smtp_sender",
    "smtp_port",
    "smtp_server",
    "org_name",
    "tls",
    "ssl",
    "use_credentials",
    "validate_certs",
)
# the settings of a mail login: each must be one the run is configured with
MAIL_CONFIGURED = (
    "smtp_username",
    "smtp_password",
    "smtp_sender",
    "smtp_port",
    "smtp_server",
)


def without_secrets(
    value: Any, drop: Sequence[str] = ("secrets", "action_code")
) -> Any:
    """A deep copy of ``value`` (JSON data) without the keys in ``drop`` at any
    depth: nothing a secret is stored in goes to the sandbox."""
    if isinstance(value, dict):
        return {
            key: without_secrets(item, drop)
            for key, item in value.items()
            if key not in drop
        }
    if isinstance(value, list):
        return [without_secrets(item, drop) for item in value]
    return copy.deepcopy(value)


def resolve_secrets(value: Any, secrets: Dict[str, str]) -> Any:
    """``value`` with every ``{"$secret": name}`` replaced by that secret's value.
    A name the run does not have is refused."""
    if isinstance(value, dict):
        if set(value) == {SECRET_KEY}:
            name = value[SECRET_KEY]
            if not isinstance(name, str) or name not in secrets:
                raise CallRefused(400, "that secret does not exist")
            return secrets[name]
        return {key: resolve_secrets(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_secrets(item, secrets) for item in value]
    return value


@dataclass
class Toolbox:
    """What the broker's handlers use, all of it built by ``run_action`` from
    the run's own data. Every callable is synchronous, as the action functions
    are; the handlers run the blocking ones off the event loop."""

    parameters: Dict[str, str]
    secrets: Dict[str, str]
    trusted_hosts: List[str]
    smtp_trusted: bool
    respondent_email: Optional[str]
    webhook: Callable[..., Any]
    discord: Callable[..., Any]
    slack: Callable[..., Any]
    config_mail: Callable[..., Any]
    send_mail: Callable[..., Any]
    append_sheet: Callable[..., Any]
    approved_recipient: Callable[[str], str]
    allow: List[Tuple[str, Optional[int]]] = field(default_factory=list)

    def configured_hosts(self) -> List[str]:
        return egress.trusted_hosts_of(
            [*self.parameters.values(), *self.secrets.values()]
        )

    def configured_values(self) -> set:
        return {str(v) for v in [*self.parameters.values(), *self.secrets.values()]}


def _reply(result: Any) -> Dict[str, Any]:
    status = getattr(result, "status_code", None)
    text = getattr(result, "text", "") or ""
    return {"status_code": status, "text": text[:REPLY_TEXT_MAX]}


def _refusal(error: Exception) -> CallRefused:
    if isinstance(error, egress.EgressRefused):
        status = 403 if error.code in ("not_allowed", "not_https") else 502
        return CallRefused(status, f"the call was refused ({error.code})")
    return CallRefused(502, "the call failed")


def build_handlers(toolbox: Toolbox) -> Dict[str, Callable[..., Awaitable[Any]]]:
    """The calls the sandbox may make, as the broker's handler table."""

    async def off_loop(function, *args):
        return await asyncio.get_running_loop().run_in_executor(None, function, *args)

    def configured_address(url: Any) -> None:
        if not isinstance(url, str):
            raise CallRefused(400, "the address must be text")
        try:
            destination = egress.check_url(
                url, allow=toolbox.allow, trusted=toolbox.trusted_hosts
            )
        except egress.EgressRefused as error:
            raise _refusal(error)
        if destination.host not in toolbox.configured_hosts() and not any(
            destination.host == host for host, _port in toolbox.allow
        ):
            raise CallRefused(
                403, "that address is not one this action is configured with"
            )

    async def outgoing(function, url, params, data, headers) -> Dict[str, Any]:
        configured_address(url)
        for name, value in (("params", params), ("headers", headers)):
            if value is not None and not isinstance(value, dict):
                raise CallRefused(400, f"{name} must be a dict")
        try:
            result = await off_loop(
                function,
                url,
                resolve_secrets(params, toolbox.secrets),
                resolve_secrets(data, toolbox.secrets),
                resolve_secrets(headers, toolbox.secrets),
            )
        except CallRefused:
            raise
        except egress.EgressRefused as error:
            raise _refusal(error)
        except ActionHTTPException as error:
            raise CallRefused(error.status_code, str(error))
        return _reply(result)

    async def send_data_webhook(url, params=None, data=None, headers=None):
        return await outgoing(toolbox.webhook, url, params, data, headers)

    async def send_data_discord(url, params=None, data=None, headers=None):
        return await outgoing(toolbox.discord, url, params, data, headers)

    async def send_data_slack(url, params=None, data=None, headers=None):
        return await outgoing(toolbox.slack, url, params, data, headers)

    async def send_mail_action(config, subject, recipient, creator_mail=False):
        if not isinstance(config, dict) or set(config) - set(MAIL_KEYS):
            raise CallRefused(400, "the mail settings are not valid")
        resolved = resolve_secrets(config, toolbox.secrets)
        configured = toolbox.configured_values()
        for key in MAIL_CONFIGURED:
            value = resolved.get(key)
            if value is None or str(value) not in configured:
                raise CallRefused(
                    403, f"{key} is not one of this action's configured settings"
                )
        try:
            port = int(resolved["smtp_port"])
        except (TypeError, ValueError):
            raise CallRefused(400, "the port is not a number")
        try:
            egress.check_smtp(
                resolved["smtp_server"],
                port,
                allow=toolbox.allow,
                trusted=toolbox.smtp_trusted,
            )
        except egress.EgressRefused as error:
            raise _refusal(error)
        recipients = [recipient] if isinstance(recipient, str) else recipient
        if (
            not isinstance(recipients, list)
            or not recipients
            or len(recipients) > MAX_RECIPIENTS
            or not all(isinstance(r, str) for r in recipients)
        ):
            raise CallRefused(400, "the recipients are not valid")
        approved: List[str] = []
        for address in recipients:
            if (
                toolbox.respondent_email
                and address.strip().casefold() == toolbox.respondent_email.casefold()
            ):
                approved.append(address)
                continue
            try:
                approved.append(await off_loop(toolbox.approved_recipient, address))
            except Exception:  # noqa: BLE001 - refused or unavailable: not sent
                raise CallRefused(403, "that recipient is not allowed")
        if not isinstance(subject, str) or len(subject) > MAX_SUBJECT:
            raise CallRefused(400, "the subject is not valid")
        mail_config = toolbox.config_mail(
            resolved["smtp_username"],
            resolved["smtp_password"],
            resolved["smtp_sender"],
            port,
            resolved["smtp_server"],
            str(resolved.get("org_name") or ""),
            bool(resolved.get("tls", True)),
            bool(resolved.get("ssl", False)),
            bool(resolved.get("use_credentials", True)),
            bool(resolved.get("validate_certs", True)),
        )
        # on the event loop: the mail is sent by a task it schedules
        return toolbox.send_mail(mail_config, subject, approved, bool(creator_mail))

    async def append_in_sheet(google_sheet_id=None, credentials=None, data=None):
        if not isinstance(google_sheet_id, str) or not any(
            google_sheet_id == str(v) for v in toolbox.parameters.values()
        ):
            raise CallRefused(
                403, "that sheet is not one this action is configured with"
            )
        resolved = resolve_secrets(credentials, toolbox.secrets)
        if not isinstance(resolved, str) or resolved not in toolbox.secrets.values():
            raise CallRefused(403, "the credentials must be this action's own")
        if (
            not isinstance(data, list)
            or len(data) > MAX_SHEET_ROWS
            or not all(
                isinstance(item, dict)
                and isinstance(item.get("title"), str)
                and isinstance(item.get("answer"), (str, int, float, type(None)))
                for item in data
            )
        ):
            raise CallRefused(400, "the rows are not valid")
        rows = [
            {
                "title": item["title"],
                "answer": "" if item["answer"] is None else str(item["answer"]),
            }
            for item in data
        ]
        try:
            return await off_loop(toolbox.append_sheet, google_sheet_id, resolved, rows)
        except ActionHTTPException as error:
            # the sheet or the grant is gone: the code sees the same exception
            raise CallRefused(error.status_code, str(error))

    return {
        "send_data_webhook": send_data_webhook,
        "send_data_discord": send_data_discord,
        "send_data_slack": send_data_slack,
        "send_mail_action": send_mail_action,
        "append_in_sheet": append_in_sheet,
    }


async def run_custom_code(
    action_code: Optional[str],
    *,
    data: Dict[str, Any],
    toolbox: Toolbox,
) -> Outcome:
    """Run the code in a fresh sandbox child with the run's data. The data is
    cleaned of every secret here; the child gets the names only."""
    cleaned = {
        "response": without_secrets(data.get("response")),
        "form": without_secrets(data.get("form")),
        "workspace": without_secrets(data.get("workspace")),
        "action": without_secrets(data.get("action")),
        "parameters": dict(toolbox.parameters),
        "secret_names": sorted(toolbox.secrets),
        "simple_response": data.get("simple_response"),
    }
    return await broker.run_code(
        action_code or "",
        cleaned,
        build_handlers(toolbox),
        memory_mb=settings.action_sandbox_memory_mb,
        cpu_seconds=settings.action_sandbox_cpu_seconds,
        timeout_seconds=settings.action_sandbox_timeout_seconds,
        max_calls=settings.action_sandbox_max_calls,
    )

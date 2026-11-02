"""Custom action code, run in the sandbox (``sandbox/``), and the calls it may make.

The code gets this run's data (the form, the response, the workspace, the merged
parameters, **the names of the secrets and none of their values**) and the
calls below. Each call is checked here, in the executor, which holds the
secrets and does the work; the sandbox holds nothing and can reach nothing:

- ``send_data_webhook`` / ``send_data_discord`` / ``send_data_slack``: only to
  an address this run is configured with (a parameter or secret of the action,
  the workspace or the form, or an operator-allowed host), and then through the
  egress rules (public https, the address checked, no redirects). A secret the
  instance's administrators stored on the action itself (not overridden by the
  workspace or the form) can only go to the exact address those administrators
  set (scheme, host, port, path and query), not just its origin: on a shared
  host (a chat service's webhook host) a creator who points the address at
  their own channel gets no instance secret, and the reply of such a call is
  not shown to the code (an endpoint that echoes the request would hand the
  secret back);
- ``send_mail_action``: the code gives the **subject and the recipients, nothing
  else**. The login, server, port and sender are always the action's configured
  SMTP group, the transport settings are the executor's, the body is the executor's
  own template, and the copy kind follows the recipient (the respondent gets the
  respondent's copy, a current workspace member the team's copy). The respondent's
  address is the one the executor holds, never the text the code passed. At most
  five recipients;
- ``append_in_sheet``: the sheet is one this run is configured with and the
  credential is the run's own stored credential. A sheet or grant that is gone
  switches the action off, decided here from the Google call, never from what the
  code says;
- a secret is passed by name (a handle the code cannot read) in headers or a
  body, and replaced by its value here.

The number of calls, their size, the time and the memory are limited; the calls
run on a pool of their own, so a slow destination holds up this run only.
"""

import asyncio
import copy
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Set, Tuple

from models.exception_enum import ExceptionType
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
BROKEN_SIGNALS = (
    ExceptionType.GOOGLE_SHEET_MISSING,
    ExceptionType.OAUTH_TOKEN_MISSING,
)

# calls of custom code run here, never on the default pool of the event loop: a
# bounded number at once, whatever the destinations do
call_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="action-call")


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


def secret_names_in(value: Any) -> Set[str]:
    """The names of the secrets ``value`` refers to."""
    if isinstance(value, dict):
        if set(value) == {SECRET_KEY}:
            return {value[SECRET_KEY]} if isinstance(value[SECRET_KEY], str) else set()
        names: Set[str] = set()
        for item in value.values():
            names |= secret_names_in(item)
        return names
    if isinstance(value, list):
        names = set()
        for item in value:
            names |= secret_names_in(item)
        return names
    return set()


@dataclass
class Toolbox:
    """What the broker's handlers use, all of it built by ``run_action`` from
    the run's own data. The callables are the action's own functions; the
    handlers run the blocking ones on ``call_pool``."""

    parameters: Dict[str, str]
    secrets: Dict[str, str]
    # origins (scheme, host, port) of the addresses in the action's own parameters
    trusted_origins: List[Tuple[str, str, int]]
    # secrets stored on the action itself and not overridden below it
    instance_secrets: Set[str]
    respondent_email: Optional[str]
    webhook: Callable[..., Any]
    discord: Callable[..., Any]
    slack: Callable[..., Any]
    # blocking: the action's SMTP group (``respondent``: the respondent's copy,
    # else the team's) checked and turned into a mail configuration
    prepare_mail: Callable[[bool], Any]
    # a coroutine function: (configuration, subject, recipients, creator_mail)
    deliver_mail: Callable[..., Awaitable[Any]]
    append_sheet: Callable[..., Any]
    approved_recipient: Callable[[str], str]
    # blocking: tell the backend this action's sheet or credential is gone
    mark_broken: Callable[[], Any]
    allow: List[Tuple[str, Optional[int]]] = field(default_factory=list)
    # exact addresses (scheme, host, port, path, query) in the action's own
    # parameters: the only places an instance secret may go. Empty: nowhere
    trusted_urls: List[egress.ExactUrl] = field(default_factory=list)

    def configured_hosts(self) -> List[str]:
        return egress.trusted_hosts_of(
            [*self.parameters.values(), *self.secrets.values()]
        )


def _reply(result: Any, show_text: bool = True) -> Dict[str, Any]:
    status = getattr(result, "status_code", None)
    text = (getattr(result, "text", "") or "") if show_text else ""
    return {"status_code": status, "text": text[:REPLY_TEXT_MAX]}


def _refusal(error: Exception) -> CallRefused:
    if isinstance(error, egress.EgressRefused):
        status = 403 if error.code in ("not_allowed", "not_https") else 502
        return CallRefused(status, f"the call was refused ({error.code})")
    return CallRefused(502, "the call failed")


def build_handlers(toolbox: Toolbox) -> Dict[str, Callable[..., Awaitable[Any]]]:
    """The calls the sandbox may make, as the broker's handler table."""

    async def off_loop(function, *args):
        return await asyncio.get_running_loop().run_in_executor(
            call_pool, function, *args
        )

    def configured_address(url: Any) -> egress.Destination:
        if not isinstance(url, str):
            raise CallRefused(400, "the address must be text")
        try:
            destination = egress.check_url(
                url, allow=toolbox.allow, trusted=toolbox.trusted_origins
            )
        except egress.EgressRefused as error:
            raise _refusal(error)
        if destination.host not in toolbox.configured_hosts() and not any(
            destination.host == host for host, _port in toolbox.allow
        ):
            raise CallRefused(
                403, "that address is not one this action is configured with"
            )
        return destination

    async def outgoing(function, url, params, data, headers) -> Dict[str, Any]:
        destination = configured_address(url)
        for name, value in (("params", params), ("headers", headers)):
            if value is not None and not isinstance(value, dict):
                raise CallRefused(400, f"{name} must be a dict")
        names = secret_names_in([params, data, headers])
        instance_used = bool(names & toolbox.instance_secrets)
        if instance_used and destination.exact not in toolbox.trusted_urls:
            # an instance-level secret goes only to the exact address the
            # administrators set, not to another path on the same host
            raise CallRefused(
                403,
                "a secret of the instance can only go to the exact address the "
                "instance's administrators set",
            )
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
        # an endpoint that echoes the request would hand an instance secret back
        return _reply(result, show_text=not instance_used)

    async def send_data_webhook(url, params=None, data=None, headers=None):
        return await outgoing(toolbox.webhook, url, params, data, headers)

    async def send_data_discord(url, params=None, data=None, headers=None):
        return await outgoing(toolbox.discord, url, params, data, headers)

    async def send_data_slack(url, params=None, data=None, headers=None):
        return await outgoing(toolbox.slack, url, params, data, headers)

    async def send_mail_action(subject=None, recipient=None):
        # only the subject and the recipients come from the code
        if not isinstance(subject, str) or not subject or len(subject) > MAX_SUBJECT:
            raise CallRefused(400, "the subject is not valid")
        recipients = [recipient] if isinstance(recipient, str) else recipient
        if (
            not isinstance(recipients, list)
            or not recipients
            or len(recipients) > MAX_RECIPIENTS
            or not all(isinstance(r, str) for r in recipients)
        ):
            raise CallRefused(400, "the recipients are not valid")
        to_respondent = False
        members: List[str] = []
        for address in recipients:
            if (
                toolbox.respondent_email
                and address.strip().casefold() == toolbox.respondent_email.casefold()
            ):
                to_respondent = True
                continue
            try:
                approved = await off_loop(toolbox.approved_recipient, address)
            except Exception:  # noqa: BLE001 - refused or unavailable: not sent
                raise CallRefused(403, "that recipient is not allowed")
            if approved not in members:
                members.append(approved)
        try:
            if to_respondent:
                config = await off_loop(toolbox.prepare_mail, True)
                # the address held here, not the text the code passed
                await toolbox.deliver_mail(
                    config, subject, [toolbox.respondent_email], False
                )
            if members:
                config = await off_loop(toolbox.prepare_mail, False)
                await toolbox.deliver_mail(config, subject, members, True)
        except egress.EgressRefused as error:
            raise _refusal(error)
        except CallRefused:
            raise
        except Exception as error:  # noqa: BLE001 - class only, no message
            logger.warning(
                "a mail of action code was not sent: %s", type(error).__name__
            )
            raise CallRefused(502, "the mail was not sent")
        return "ok"

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
            # The executor's own Google call found the sheet or the grant gone:
            # only that signal switches the action off, never a code's say-so.
            if str(error) in BROKEN_SIGNALS:
                await off_loop(toolbox.mark_broken)
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

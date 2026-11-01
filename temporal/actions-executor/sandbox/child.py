"""The sandbox child: ``python -I child.py <memory_mb> <cpu_seconds> <scratch dir>``,
one per run, started by the broker (``broker.py``) with an empty environment, an
empty working directory and nothing open but stdin and stdout.

It imports everything it will need, confines itself (``confine.py``: no file, no
socket, no ``execve``, limits), reports what took effect, and only then reads
the run: the code and the data of this one run (no secret value, no key).
The code's only way to the outside world is :func:`_call`, one JSON line to the
broker over stdout and one answer back over stdin; the broker decides.

The names the code can use are the whole of its world: the handful of builtins
below, the run's data as plain dicts and lists, and the functions defined here.
There is no ``import`` (policy.py), no ``getattr`` and no module object.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Everything the child will ever import, before the filesystem goes away.
import ast  # noqa: E402,F401
import builtins  # noqa: E402
import ctypes  # noqa: E402,F401
import encodings.idna  # noqa: E402,F401
import encodings.utf_8  # noqa: E402,F401
import json  # noqa: E402
import math  # noqa: E402,F401
import random  # noqa: E402
import re  # noqa: E402,F401
import resource  # noqa: E402,F401
import struct  # noqa: E402,F401
import unicodedata  # noqa: E402,F401
from types import SimpleNamespace  # noqa: E402

from sandbox import confine, policy  # noqa: E402

MAX_LINE = 8 * 1024 * 1024
LOG_LINE_MAX = 2000

_read_line = sys.stdin.buffer.readline


class HTTPException(Exception):
    """What the code raises or catches for a refused or failed outside call."""

    def __init__(self, status_code, content=None):
        super().__init__(content)
        self.status_code = status_code
        self.content = content

    def __str__(self):
        return "" if self.content is None else str(self.content)


class Secret:
    """A stored secret as the code can hold it: a name and nothing else. Passed
    back in a call's headers, body or mail login it is replaced by the value in
    the broker; it has no value here to print, log or send anywhere else."""

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<secret {self.name}>"

    __str__ = __repr__


class Reply:
    """The answer to an outside call: ``status_code``, ``ok`` and ``text``
    (the first part of the body)."""

    def __init__(self, status_code, text):
        self.status_code = status_code
        self.ok = isinstance(status_code, int) and 200 <= status_code < 400
        self.text = text


def _encode(value):
    if isinstance(value, Secret):
        return {"$secret": value.name}
    raise TypeError("not something an outside call can carry")


def _send(message):
    data = json.dumps(message, default=_encode, separators=(",", ":")).encode()
    data += b"\n"
    view = memoryview(data)
    while view:
        written = os.write(1, view)
        view = view[written:]


def _receive():
    line = _read_line(MAX_LINE + 1)
    if not line or len(line) > MAX_LINE:
        os._exit(4)
    return json.loads(line)


_calls = 0


def _call(method, **arguments):
    global _calls
    _calls += 1
    _send({"t": "call", "id": _calls, "m": method, "a": arguments})
    reply = _receive()
    if reply.get("ok"):
        return reply.get("v")
    raise HTTPException(reply.get("status", 400), reply.get("e", "refused"))


def _reply(value):
    if not isinstance(value, dict):
        return value
    return Reply(value.get("status_code"), value.get("text", ""))


SAFE_BUILTIN_NAMES = (
    "abs all any bool dict enumerate filter float int isinstance len list map max "
    "min range repr reversed round set sorted str sum tuple zip "
    "Exception ValueError KeyError IndexError TypeError ZeroDivisionError "
    "AttributeError RuntimeError StopIteration"
).split()


def _api(data, log):
    """The names the code runs with (everything else is a NameError)."""
    parameters = dict(data.get("parameters") or {})
    secret_names = list(data.get("secret_names") or [])
    response = data.get("response")
    form = data.get("form")
    workspace = data.get("workspace")
    simple = data.get("simple_response")

    def get_parameters():
        return dict(parameters)

    def get_parameter(key):
        return parameters.get(key)

    def get_secrets():
        return {name: Secret(name) for name in secret_names}

    def get_secret(key):
        return Secret(key) if key in secret_names else None

    def get_form():
        return form

    def get_response():
        return response

    def get_state():
        state = (response or {}).get("state") or {}
        return state.get("global_state") if isinstance(state, dict) else None

    def get_workspace_details():
        return workspace

    def get_simple_form_response():
        return simple

    def send_data_webhook(url, params=None, data=None, headers=None):
        return _reply(
            _call(
                "send_data_webhook",
                url=url,
                params=params,
                data=data,
                headers=headers,
            )
        )

    def send_data_discord(url, params=None, data=None, headers=None):
        return _reply(
            _call(
                "send_data_discord", url=url, params=params, data=data, headers=headers
            )
        )

    def send_data_slack(url, params=None, data=None, headers=None):
        return _reply(
            _call("send_data_slack", url=url, params=params, data=data, headers=headers)
        )

    def config_mail(
        smtp_username,
        smtp_password,
        smtp_sender,
        smtp_port,
        smtp_server,
        org_name="",
        tls=True,
        ssl=False,
        use_credentials=True,
        validate_certs=True,
    ):
        return {
            "smtp_username": smtp_username,
            "smtp_password": smtp_password,
            "smtp_sender": smtp_sender,
            "smtp_port": smtp_port,
            "smtp_server": smtp_server,
            "org_name": org_name,
            "tls": tls,
            "ssl": ssl,
            "use_credentials": use_credentials,
            "validate_certs": validate_certs,
        }

    def send_mail_action(config, subject, recipient, creator_mail=False):
        return _call(
            "send_mail_action",
            config=config,
            subject=subject,
            recipient=recipient,
            creator_mail=creator_mail,
        )

    def append_in_sheet(google_sheet_id=None, credentials=None, data=None):
        return _call(
            "append_in_sheet",
            google_sheet_id=google_sheet_id,
            credentials=credentials,
            data=data,
        )

    return {
        "log": log,
        "json": SimpleNamespace(dumps=json.dumps, loads=json.loads),
        "random": random.Random,
        "HTTPException": HTTPException,
        "response": response,
        "form": form,
        "action": data.get("action"),
        "workspace": workspace,
        "get_form": get_form,
        "get_response": get_response,
        "get_parameters": get_parameters,
        "get_secrets": get_secrets,
        "get_parameter": get_parameter,
        "get_secret": get_secret,
        "get_state": get_state,
        "get_workspace_details": get_workspace_details,
        "get_simple_form_response": get_simple_form_response,
        "send_data_webhook": send_data_webhook,
        "send_data_discord": send_data_discord,
        "send_data_slack": send_data_slack,
        "config_mail": config_mail,
        "send_mail_action": send_mail_action,
        "append_in_sheet": append_in_sheet,
    }


def _safe_builtins(log):
    names = {name: getattr(builtins, name) for name in SAFE_BUILTIN_NAMES}
    names["print"] = lambda *args, **kwargs: log(" ".join(str(a) for a in args))
    return names


def run(request, validate=True):
    """Run the request's code; the outcome as a dict (never raises)."""
    lines = []
    size = 0
    log_cap = int(request.get("max_log_bytes", 64 * 1024))

    def log(message):
        nonlocal size
        text = str(message)[:LOG_LINE_MAX]
        if size + len(text) > log_cap:
            return
        size += len(text) + 1
        lines.append(text)

    error = None
    try:
        code = request.get("code") or ""
        if validate:
            tree = policy.check_source(code)
            compiled = compile(tree, "<action>", "exec")
            namespace = {"__builtins__": _safe_builtins(log), "__name__": "action"}
            namespace.update(_api(request.get("data") or {}, log))
        else:
            # tests only: the code gets real builtins, to show that the process
            # holds when the policy layer does not
            compiled = compile(code, "<action>", "exec")
            namespace = {"__builtins__": builtins, "log": log, "_call": _call}
        exec(compiled, namespace)
    except policy.PolicyViolation as violation:
        error = {"kind": "refused", "message": str(violation)}
    except HTTPException as exception:
        error = {"kind": "http", "message": str(exception)[:1000]}
    except MemoryError:
        error = {"kind": "memory", "message": "the code used too much memory"}
    except RecursionError:
        error = {"kind": "error", "class": "RecursionError", "message": ""}
    except Exception as exception:  # noqa: BLE001 - reported by class
        error = {
            "kind": "error",
            "class": type(exception).__name__,
            "message": str(exception)[:1000],
        }
    return {"t": "done", "log": lines, "error": error}


def main(argv):
    memory_mb, cpu_seconds, scratch = int(argv[0]), int(argv[1]), argv[2]
    try:
        facts = confine.apply(memory_mb, cpu_seconds, scratch)
    except Exception as exception:  # noqa: BLE001 - the broker sees the exit
        _send({"t": "ready", "facts": {"error": type(exception).__name__}})
        return 3
    _send({"t": "ready", "facts": facts})
    request = _receive()
    if request.get("t") != "run":
        return 5
    _send(run(request, validate=request.get("validate", True)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

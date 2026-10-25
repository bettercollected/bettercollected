"""The SMTP settings of a mail action are one group, never mixed.

An action carries defaults the instance's administrators set (including the
SMTP server and its login). A workspace, or one of its forms, may override
parameters of the action. Merged name by name, a workspace that overrode only
the server would send the instance's login to its own server.

The rule: if the workspace or the form supplies ANY member of the group (the
server, port, user name, password or sender, as a parameter or a secret), the
whole group comes from the workspace and the form, and the instance's values
of the group are dropped. Whatever the override leaves out stays empty and the
send is refused, naming the missing settings. If neither supplies a member,
the whole group is the instance's. Values are only ever read from one side.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# the names the mail actions read (the first four parameters, Password a
# secret), compared ignoring case and punctuation
SMTP_GROUP = ("server", "Port", "Username", "Password", "Sender")
_REQUIRED = SMTP_GROUP


def _normal(name: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


_GROUP_NAMES = {_normal(name) for name in SMTP_GROUP}


def in_smtp_group(name: Any) -> bool:
    """Whether a parameter or secret name belongs to the SMTP group: one of the
    group's names, or anything that names itself SMTP (custom actions)."""
    if name is None:
        return False
    normal = _normal(name)
    return normal in _GROUP_NAMES or normal.startswith("smtp")


def _is_set(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    name, value = item.get("name"), item.get("value")
    return name is not None and value is not None and value != ""


def _overrides(owner: Optional[Dict[str, Any]], key: str, action_id: Any) -> List[Any]:
    bag = (owner or {}).get(key) or {}
    if not isinstance(bag, dict):
        return []
    return list(bag.get(action_id) or [])


def smtp_overridden(
    action: Dict[str, Any], workspace: Optional[Dict[str, Any]], form: Dict[str, Any]
) -> bool:
    """Whether the workspace or the form sets any SMTP setting of this action
    (a parameter or a secret; an empty value is no override)."""
    action_id = action.get("id")
    for owner in (workspace, form):
        for key in ("parameters", "secrets"):
            for item in _overrides(owner, key, action_id):
                if _is_set(item) and in_smtp_group(item.get("name")):
                    return True
    return False


def merge_layers(
    instance: Dict[str, Any],
    workspace: Dict[str, Any],
    form: Dict[str, Any],
    group_overridden: bool,
) -> Dict[str, Any]:
    """The action's values, then the workspace's, then the form's, by name. When
    ``group_overridden``, the instance's SMTP group is left out of the base."""
    base = {
        name: value
        for name, value in instance.items()
        if not (group_overridden and in_smtp_group(name))
    }
    return {**base, **workspace, **form}


class SmtpConfigurationError(ValueError):
    """The SMTP settings are incomplete. Names only, never a value."""


def smtp_settings(
    parameters: Dict[str, Any], secrets: Dict[str, Any]
) -> Tuple[str, str, str, int, str]:
    """``(username, password, sender, port, server)`` or a clear error naming
    the settings that are missing (an override that left some out)."""

    def value(name: str) -> Any:
        return (secrets if name == "Password" else parameters).get(name)

    missing = [name for name in _REQUIRED if value(name) in (None, "")]
    if missing:
        raise SmtpConfigurationError(
            "The SMTP settings are incomplete, missing: " + ", ".join(missing)
        )
    try:
        port = int(value("Port"))
    except (TypeError, ValueError):
        raise SmtpConfigurationError("The SMTP port is not a number") from None
    return (
        value("Username"),
        value("Password"),
        value("Sender"),
        port,
        value("server"),
    )

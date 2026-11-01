"""The switch for option sources: ``OPTION_SOURCES_ENABLED``.

Off by default (a creator-configurable feature that is not released yet).
While it is off, a save that gives a question a new or changed ``optionSource``
(or creates an option list) is refused, 422 ``option_sources_disabled``, on
every path. What is stored keeps working for **workspace lists**: a question
with a list source is still served its options, validated and exported, and
lists are still readable.

It is also the kill switch for **another form's answers**: while it is off
nothing is offered from them (the respondent route answers "unavailable", a
submission with a new choice from them is refused, the builder preview is
empty). Answers already stored keep their label snapshots.
"""

DISABLED_CODE = "option_sources_disabled"
DISABLED_MESSAGE = (
    "Options from a list or from another form's answers cannot be added or "
    "changed on this server yet (OPTION_SOURCES_ENABLED is off). A question "
    "that already has a source keeps it."
)


def option_sources_enabled() -> bool:
    """Is ``OPTION_SOURCES_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "OPTION_SOURCES_ENABLED", False))

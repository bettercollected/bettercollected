"""The tables of the Open Formulieren format and of how it maps to our forms.

Kept in one module of plain data so that the importer reads them forwards and
an export can read them backwards. Format facts (entry names, keys, component
type names, JSON logic operators, action types) are cited in
docs/open-formulieren.md against release 4.0.6; the names here are the
format's own, the structure and code are ours.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional

# ---------------------------------------------------------------- archive

ENTRY_FORM = "forms.json"
ENTRY_STEPS = "formSteps.json"
ENTRY_DEFINITIONS = "formDefinitions.json"
ENTRY_LOGIC = "formLogic.json"
ENTRY_VARIABLES = "formVariables.json"
ENTRY_META = "_meta.json"
KNOWN_ENTRIES: FrozenSet[str] = frozenset(
    {
        ENTRY_FORM,
        ENTRY_STEPS,
        ENTRY_DEFINITIONS,
        ENTRY_LOGIC,
        ENTRY_VARIABLES,
        ENTRY_META,
    }
)
# an archive without these is not an export of a form (logic and variables
# may be missing; an export always writes them, empty when there are none)
REQUIRED_ENTRIES = (ENTRY_FORM, ENTRY_STEPS, ENTRY_DEFINITIONS, ENTRY_META)

SOURCE_KIND = "open_formulieren"

# ---------------------------------------------------------------- reasons
# The stable reason codes of the report (docs/open-formulieren.md); the webapp
# keeps the sentences, keyed by them.


class Reason:
    # components
    UNSUPPORTED_TYPE = "unsupported_component_type"
    UNKNOWN_TYPE = "unknown_component_type"
    ALWAYS_HIDDEN = "always_hidden"
    NOT_IN_GROUP = "not_allowed_in_repeating_group"
    CONVERTED_TO_TEXT = "converted_to_text"
    CONVERTED_TO_NUMBER = "converted_to_number"
    CONVERTED_TO_YES_NO = "converted_to_yes_no"
    DATETIME_SPLIT = "datetime_split"
    CHECKBOX_REQUIRED = "checkbox_required_not_enforced"
    NATIONAL_ID = "national_identity_number"
    MULTIPLE = "multiple_not_supported"
    CHOICES_FROM_VARIABLE = "choices_from_variable"
    TOO_FEW_CHOICES = "too_few_choices"
    DEFAULT_VALUE = "default_value_not_carried"
    VALIDATION = "validation_not_carried"
    FILE_RESTRICTIONS = "file_restrictions_not_carried"
    HTML_SIMPLIFIED = "html_simplified"
    CUSTOM_SCRIPT = "custom_script_dropped"
    PREFILL = "prefill_not_carried"
    DATE_RULE = "date_rule_not_carried"
    DISABLED = "disabled_not_carried"
    SECOND_TEXT = "second_text_not_carried"
    EMPTY_STEP = "empty_step"
    EMPTY_GROUP = "empty_group"
    REJECTED = "rejected_by_form_rules"
    # logic
    TRIGGER = "trigger_not_supported"
    ACTION = "action_not_supported"
    CONFLICT = "conflicting_rules"
    SOURCE_MISSING = "condition_source_missing"
    SOURCE_LATER = "condition_source_later"
    TARGET_MISSING = "target_missing"
    VALUE = "condition_value_not_supported"
    # variables
    USER_VARIABLE = "user_variable_not_carried"
    # features and settings
    SIGN_IN = "sign_in_not_carried"
    PAYMENT = "payment_not_carried"
    APPOINTMENT = "appointment_not_carried"
    REGISTRATION = "registration_not_carried"
    TRANSLATIONS = "translations_not_carried"
    PRESENTATION = "presentation_not_carried"
    STATEMENT_OF_TRUTH = "statement_of_truth_not_carried"
    PRIVACY_POLICY = "privacy_policy_missing"
    PURPOSE = "purpose_missing"
    RETENTION_GLOBAL = "retention_global_setting"
    RETENTION_METHOD = "retention_method_not_carried"
    RETENTION_OTHER = "retention_other_limits_not_carried"
    SCHEDULE = "schedule_not_carried"
    ERROR_MESSAGES = "error_messages_not_carried"
    REGISTRATION_ATTRIBUTE = "registration_attribute_not_carried"
    # archive
    ENTRY_IGNORED = "archive_entry_ignored"


# ------------------------------------------------------------- components

# answer patterns of the converted types (plain text answers)
TIME_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
IBAN_PATTERN = r"^[A-Za-z]{2}[0-9]{2}[A-Za-z0-9 ]{11,30}$"
NATIONAL_ID_PATTERN = r"^[0-9]{9}$"
POSTCODE_PATTERN = r"^[1-9][0-9]{3} ?[A-Za-z]{2}$"


@dataclass(frozen=True)
class TypeRule:
    """How one component type becomes one of our question types."""

    ours: str  # StandardFormFieldType value
    # how a condition reads the answer: text | number | date | choice | yes_no
    kind: str = "text"
    # the reason to report when the shape changes (None: a plain mapping)
    converted: Optional[str] = None
    pattern: Optional[str] = None
    placeholder: Optional[str] = None
    national_id: bool = False


TYPE_RULES: Dict[str, TypeRule] = {
    "textfield": TypeRule("short_text"),
    "textarea": TypeRule("long_text"),
    "email": TypeRule("email"),
    "number": TypeRule("number", kind="number"),
    "currency": TypeRule("number", kind="number", converted=Reason.CONVERTED_TO_NUMBER),
    "phoneNumber": TypeRule("phone_number"),
    "date": TypeRule("date", kind="date"),
    "time": TypeRule(
        "short_text",
        converted=Reason.CONVERTED_TO_TEXT,
        pattern=TIME_PATTERN,
        placeholder="HH:MM",
    ),
    "postcode": TypeRule(
        "short_text", converted=Reason.CONVERTED_TO_TEXT, pattern=POSTCODE_PATTERN
    ),
    "iban": TypeRule(
        "short_text", converted=Reason.CONVERTED_TO_TEXT, pattern=IBAN_PATTERN
    ),
    "licenseplate": TypeRule("short_text", converted=Reason.CONVERTED_TO_TEXT),
    "bsn": TypeRule("short_text", pattern=NATIONAL_ID_PATTERN, national_id=True),
    "select": TypeRule("dropdown", kind="choice"),
    "radio": TypeRule("multiple_choice", kind="choice"),
    "selectboxes": TypeRule("multiple_choice", kind="choice"),
    "checkbox": TypeRule(
        "yes_no", kind="yes_no", converted=Reason.CONVERTED_TO_YES_NO
    ),
    "file": TypeRule("file_upload"),
    "content": TypeRule("text"),
    # datetime is two questions (see the importer); its date half is this
    "datetime": TypeRule("date", kind="date"),
}

CHOICE_TYPES: FrozenSet[str] = frozenset({"select", "radio", "selectboxes"})
# the question types a repeating group's children may have (the form
# model's REPEAT_CHILD_FIELD_TYPES) are checked against ``ours``, not here
LAYOUT_TYPES: FrozenSet[str] = frozenset({"fieldset", "columns"})
GROUP_TYPES: FrozenSet[str] = frozenset({"editgrid"})
# kept apart: types that need a register lookup, a map, a second signer or a
# signature: no equivalent in our questions
UNSUPPORTED_TYPES: FrozenSet[str] = frozenset(
    {
        "signature",
        "map",
        "addressNL",
        "partners",
        "children",
        "npFamilyMembers",
        "cosign",
        "coSign",
        "customerProfile",
    }
)
# internal helper components: no meaning here, not worth a report line
SILENT_TYPES: FrozenSet[str] = frozenset({"softRequiredErrors"})

# keys that hold code in older definitions (never read as code, only noticed)
SCRIPT_KEYS = ("customConditional", "calculateValue", "customDefaultValue")
SCRIPT_VALIDATE_KEYS = ("custom",)

# ------------------------------------------------------------------ logic

# JSON logic comparison operators we translate (matched by name only; the
# expression is walked as data, never run)
COMPARISONS: Dict[str, str] = {
    "==": "IS_EQUAL",
    "===": "IS_EQUAL",
    "!=": "IS_NOT_EQUAL",
    "!==": "IS_NOT_EQUAL",
    ">": "GREATER_THAN",
    ">=": "GREATER_THAN_EQUAL",
    "<": "LESS_THAN",
    "<=": "LESS_THAN_EQUAL",
}
NEGATIONS: Dict[str, str] = {
    "IS_EQUAL": "IS_NOT_EQUAL",
    "IS_NOT_EQUAL": "IS_EQUAL",
    "GREATER_THAN": "LESS_THAN_EQUAL",
    "LESS_THAN_EQUAL": "GREATER_THAN",
    "GREATER_THAN_EQUAL": "LESS_THAN",
    "LESS_THAN": "GREATER_THAN_EQUAL",
    "IS_EMPTY": "IS_NOT_EMPTY",
    "IS_NOT_EMPTY": "IS_EMPTY",
}
# comparisons that make sense for each answer kind
KIND_COMPARISONS: Dict[str, FrozenSet[str]] = {
    "text": frozenset({"IS_EQUAL", "IS_NOT_EQUAL", "IS_EMPTY", "IS_NOT_EMPTY"}),
    "date": frozenset({"IS_EQUAL", "IS_NOT_EQUAL", "IS_EMPTY", "IS_NOT_EMPTY"}),
    "choice": frozenset({"IS_EQUAL", "IS_NOT_EQUAL", "IS_EMPTY", "IS_NOT_EMPTY"}),
    "yes_no": frozenset({"IS_EQUAL", "IS_NOT_EQUAL"}),
    "number": frozenset(
        {
            "IS_EQUAL",
            "IS_NOT_EQUAL",
            "GREATER_THAN",
            "GREATER_THAN_EQUAL",
            "LESS_THAN",
            "LESS_THAN_EQUAL",
            "IS_EMPTY",
            "IS_NOT_EMPTY",
        }
    ),
}

# the action types of a logic rule (the format's own names)
ACTION_PROPERTY = "property"
ACTION_TYPES: FrozenSet[str] = frozenset(
    {
        "step-not-applicable",
        "step-applicable",
        "disable-next",
        "property",
        "variable",
        "fetch-from-service",
        "set-registration-backend",
        "evaluate-dmn",
        "synchronize-variables",
    }
)

# our yes/no answers
YES = "Yes"
NO = "No"

# ----------------------------------------------------------- form settings

FEATURE_KEYS_PRESENTATION = (
    "confirmation_email_template",
    "literals",
    "help_callout_page",
    "help_dialog",
    "theme",
    "category",
    "product",
)

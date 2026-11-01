# Generated from docs/spec/form-spec-v1.schema.json by scripts/generate.py. Do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class Attachment(BaseModel):
    """
    An image or video shown with a question or a choice.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    type: Literal["image", "video"] | None = Field(None, title="Type")
    href: str | None = Field(None, title="Href")
    scale: float | None = Field(None, title="Scale")
    description: str | None = Field(None, title="Description")
    embed_provider: Literal["youtube", "vimeo", "no_embed"] | None = Field(
        None, alias="embedProvider", title="Embedprovider"
    )


class Decimals(RootModel[int]):
    root: int = Field(None, ge=0, le=6, title="Decimals")


class Currency(RootModel[str]):
    root: str = Field(
        None,
        description="ISO 4217 code; EUR by default.",
        pattern="^[A-Z]{3}$",
        title="Currency",
    )


class CalculationFormat(BaseModel):
    """
    How a calculated field shows its value (display only; the stored
    value is the computed one).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    style: Literal["number", "currency", "percent", "text"] | None = Field(
        None,
        description="number (default), currency, percent (0.25 shows as 25%) or text.",
        title="Style",
    )
    decimals: Decimals | None = Field(None, title="Decimals")
    currency: Currency | None = Field(
        None, description="ISO 4217 code; EUR by default.", title="Currency"
    )


class Condition(BaseModel):
    """
    One condition of a visibility rule or a page jump: the answer of
    ``fieldId`` compared with ``value`` (a choice's value, "Yes"/"No" for a
    yes/no question). On a repeating group, ``groupMode`` COUNT compares
    the number of items; ANY / ALL test ``childFieldId`` in the items.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    field_id: str | None = Field(None, alias="fieldId", title="Fieldid")
    field_type: str | None = Field(
        None,
        alias="fieldType",
        description="Type of the source question (filled in by the editor).",
        title="Fieldtype",
    )
    comparison: (
        Literal[
            "IS_EMPTY",
            "IS_NOT_EMPTY",
            "IS_EQUAL",
            "IS_NOT_EQUAL",
            "CONTAINS",
            "DOES_NOT_CONTAIN",
            "LESS_THAN",
            "LESS_THAN_EQUAL",
            "GREATER_THAN",
            "GREATER_THAN_EQUAL",
            "STARTS_WITH",
            "ENDS_WITH",
        ]
        | None
    ) = Field(None, title="Comparison")
    value: Any = Field(None, title="Value")
    group_mode: Literal["COUNT", "ANY", "ALL"] | None = Field(
        None, alias="groupMode", title="Groupmode"
    )
    child_field_id: str | None = Field(None, alias="childFieldId", title="Childfieldid")
    child_field_type: str | None = Field(
        None, alias="childFieldType", title="Childfieldtype"
    )


class DateRule(BaseModel):
    """
    The chosen date must be ``comparison`` a fixed ``date`` (YYYY-MM-DD),
    today, or the answer of another date question (``fieldId``).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    comparison: Literal["before", "after", "on_or_before", "on_or_after"] = Field(
        ..., title="Comparison"
    )
    target: Literal["date", "today", "field"] = Field(..., title="Target")
    date: str | None = Field(None, title="Date")
    field_id: str | None = Field(None, alias="fieldId", title="Fieldid")


class Id(RootModel[str]):
    root: str = Field(
        None,
        description="Stable id that page jumps name. Given when left out.",
        pattern="^[A-Za-z0-9_-]{1,64}$",
        title="Id",
    )


class Name(RootModel[str]):
    root: str = Field(
        None,
        description="Short internal name, e.g. Eligible. Respondents never see it.",
        max_length=60,
        title="Name",
    )


class Title(RootModel[str]):
    root: str = Field(None, max_length=300, title="Title")


class Message(RootModel[str]):
    root: str = Field(None, max_length=5000, title="Message")


class ButtonText(RootModel[str]):
    root: str = Field(None, max_length=80, title="Buttontext")


class ColSpan(RootModel[int]):
    root: int = Field(
        None,
        description="Width on a 12-column grid (12 = full row).",
        ge=1,
        le=12,
        title="Colspan",
    )


class Label(RootModel[str]):
    root: str = Field(
        None,
        description="Short label shown with a date picker.",
        max_length=120,
        title="Label",
    )


class DateRules(RootModel[list[DateRule]]):
    root: list[DateRule] = Field(
        None,
        description="Constraints on a date or day question's answer.",
        max_length=5,
        title="Daterules",
    )


class MinTime(RootModel[str]):
    root: str = Field(
        None,
        description="A time question: the earliest time that can be answered (HH:MM, 24-hour).",
        pattern="^([01][0-9]|2[0-3]):[0-5][0-9]$",
        title="Mintime",
    )


class MaxTime(RootModel[str]):
    root: str = Field(
        None,
        description="A time question: the latest time that can be answered (HH:MM, 24-hour).",
        pattern="^([01][0-9]|2[0-3]):[0-5][0-9]$",
        title="Maxtime",
    )


class Currencies(RootModel[list[str]]):
    root: list[str] = Field(
        None,
        description="A currency question: the ISO 4217 codes respondents may pick (the first is the default). Amounts are answered with min/max in validations.",
        max_length=10,
        min_length=1,
        title="Currencies",
    )


class Countries(RootModel[list[str]]):
    root: list[str] = Field(
        None,
        description="An address question: the ISO 3166-1 alpha-2 codes of the countries respondents may give (default: NL only).",
        max_length=30,
        min_length=1,
        title="Countries",
    )


class WhyWeAsk(RootModel[str]):
    root: str = Field(None, max_length=280, title="Whyweask")


class Layout(
    RootModel[
        Literal[
            "TWO_COLUMN_IMAGE_LEFT",
            "TWO_COLUMN_IMAGE_RIGHT",
            "SINGLE_COLUMN_IMAGE_BACKGROUND",
            "SINGLE_COLUMN_NO_BACKGROUND",
            "SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN",
        ]
    ]
):
    root: Literal[
        "TWO_COLUMN_IMAGE_LEFT",
        "TWO_COLUMN_IMAGE_RIGHT",
        "SINGLE_COLUMN_IMAGE_BACKGROUND",
        "SINGLE_COLUMN_NO_BACKGROUND",
        "SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN",
    ] = Field(
        ...,
        description="How a page, the welcome page or an ending is laid out.",
        title="Layout",
    )


class Logic(BaseModel):
    """
    Show or hide this question when its conditions match (operator:
    AND = all, OR = any; AND when absent).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    action: Literal["SHOW", "HIDE"] | None = Field(None, title="Action")
    operator: Literal["AND", "OR"] | None = Field(None, title="Operator")
    conditions: list[Condition] | None = Field(None, title="Conditions")


class Alt(RootModel[str]):
    root: str = Field(None, max_length=150, title="Alt")


class Logo(BaseModel):
    """
    The organisation logo at the top of every respondent page.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    url: str | None = Field(
        None,
        description="Set by uploading a logo; ignored when a document is written.",
        title="Url",
    )
    position: Literal["auto", "left", "center"] | None = Field(None, title="Position")
    alt: Alt | None = Field(None, title="Alt")
    use_workspace_logo: bool | None = Field(
        None, alias="useWorkspaceLogo", title="Useworkspacelogo"
    )


class OptionFilterEntry(BaseModel):
    """
    While the earlier question's option ``when`` (its id) is chosen, the
    question offers the options in ``show`` (their ids).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    when: str = Field(..., max_length=200, min_length=1, title="When")
    show: list[str] | None = Field(None, max_length=2000, title="Show")


class ListId(RootModel[str]):
    root: str = Field(None, max_length=64, title="Listid")


class ParentFieldId(RootModel[str]):
    root: str = Field(None, max_length=64, title="Parentfieldid")


class FormId(RootModel[str]):
    root: str = Field(None, max_length=64, title="Formid")


class QuestionId(RootModel[str]):
    root: str = Field(None, max_length=64, title="Questionid")


class OptionSource(BaseModel):
    """
    Where a dropdown or multiple choice question's options come from
    instead of ``choices``: ``kind`` ``list`` (a workspace's option list,
    ``listId``; ``parentFieldId`` names an earlier choice question whose
    answer narrows the list by each item's group) or ``form_answers`` (the
    answers to question ``questionId`` of another form ``formId`` of the same
    workspace; the saver needs permission to read that form's responses).
    A question has either a source or ``choices``, never both. Checked by
    the server on every save and again on every submission.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    kind: Literal["list", "form_answers"] = Field(..., title="Kind")
    list_id: ListId | None = Field(None, alias="listId", title="Listid")
    parent_field_id: ParentFieldId | None = Field(
        None, alias="parentFieldId", title="Parentfieldid"
    )
    form_id: FormId | None = Field(None, alias="formId", title="Formid")
    question_id: QuestionId | None = Field(None, alias="questionId", title="Questionid")


class SectionTitle(RootModel[str]):
    root: str = Field(None, max_length=120, title="Sectiontitle")


class EndingId(RootModel[str]):
    root: str = Field(
        None,
        description='The id of an ending of this form; only with target "__SUBMIT__".',
        pattern="^[A-Za-z0-9_-]{1,64}$",
        title="Endingid",
    )


class PageJump(BaseModel):
    """
    After this page, go to ``target`` (a page id, or "__SUBMIT__" to
    end the form) when the conditions match. The first matching jump wins;
    no match goes to the next page. With "__SUBMIT__", ``endingId`` names
    the ending shown after submitting (default: the form's default
    ending).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    operator: Literal["AND", "OR"] | None = Field(None, title="Operator")
    conditions: list[Condition] | None = Field(None, title="Conditions")
    target: str | None = Field(None, title="Target")
    ending_id: EndingId | None = Field(
        None,
        alias="endingId",
        description='The id of an ending of this form; only with target "__SUBMIT__".',
        title="Endingid",
    )


class Position(BaseModel):
    """
    Where a page sits on the flow view's canvas (cosmetic).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    x: float | None = Field(None, title="X")
    y: float | None = Field(None, title="Y")


class MinItems(RootModel[int]):
    root: int = Field(None, ge=0, le=50, title="Minitems")


class MaxItems(RootModel[int]):
    root: int = Field(None, ge=1, le=50, title="Maxitems")


class ItemLabel(RootModel[str]):
    root: str = Field(None, max_length=80, title="Itemlabel")


class ItemTitle(RootModel[str]):
    root: str = Field(None, max_length=300, title="Itemtitle")


class Repeat(BaseModel):
    """
    Makes a group repeatable: its questions are answered once per item.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    min_items: MinItems | None = Field(None, alias="minItems", title="Minitems")
    max_items: MaxItems | None = Field(None, alias="maxItems", title="Maxitems")
    item_label: ItemLabel | None = Field(None, alias="itemLabel", title="Itemlabel")
    item_title: ItemTitle | None = Field(None, alias="itemTitle", title="Itemtitle")
    export_layout: Literal["columns", "rows"] | None = Field(
        None, alias="exportLayout", title="Exportlayout"
    )


class Retention(BaseModel):
    """
    How long answers are kept: a number of days, until a date
    (YYYY-MM-DD), or forever.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    type: Literal["days", "date", "forever"] = Field(..., title="Type")
    value: int | str | None = Field(None, title="Value")


class RuleSetValue(BaseModel):
    """
    The value a rule gives the question: a fixed ``const`` (a text, a
    number, true/false for yes/no, a YYYY-MM-DD date, or the ``id`` of one of
    a choice question's options) or an ``expression``, never both.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    const: bool | int | float | str | None = Field(
        None,
        description="A choice question is set by the id of one of its options.",
        title="Const",
    )
    expression: Any = Field(None, title="Expression")


class Title1(RootModel[str]):
    root: str = Field(
        None,
        description="Plain text; may pipe answers ({{field:<id>}}).",
        max_length=300,
        title="Title",
    )


class Description(RootModel[str]):
    root: str = Field(None, max_length=1000, title="Description")


class RuleThen(BaseModel):
    """
    What a rule does while it is active (at least one key). The server
    enforces ``required``, ``readOnly`` and ``setValue``; ``title`` and
    ``description`` only change what respondents read.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    required: bool | None = Field(
        None,
        description="true: the question must be answered; false: it is optional.",
        title="Required",
    )
    read_only: Literal[True] | None = Field(
        None,
        alias="readOnly",
        description="Respondents cannot change the value: a submitted value is discarded (replaced by an active setValue, else removed).",
        title="Readonly",
    )
    title: Title1 | None = Field(
        None,
        description="Plain text; may pipe answers ({{field:<id>}}).",
        title="Title",
    )
    description: Description | None = Field(None, title="Description")
    set_value: RuleSetValue | None = Field(
        None,
        alias="setValue",
        description="The server computes the value and stores it, whatever a client sent; an empty result leaves the question unanswered. Implies readOnly.",
    )


class Conditions(RootModel[list[Condition]]):
    root: list[Condition] = Field(None, max_length=20, min_length=1, title="Conditions")


class RuleWhen(BaseModel):
    """
    When a rule is active: ``conditions`` (as in ``logic``; operator AND
    when absent) or an expressions-v1 ``expression`` (active when its value
    is truthy), never both.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    operator: Literal["AND", "OR"] | None = Field(None, title="Operator")
    conditions: Conditions | None = Field(None, title="Conditions")
    expression: Any = Field(
        None,
        description="An expressions-v1 syntax tree (docs/spec/expressions-v1.md) over the form's variables; inside a repeating group a sibling question's id reads that item's answer.",
        title="Expression",
    )


class Highlight(RootModel[str]):
    root: str = Field(
        None,
        description="The chosen answer, the 'why we ask' and 'optional' notes and, where it reads, the focus ring. Absent: secondary.",
        pattern="^#[0-9a-fA-F]{6}$",
        title="Highlight",
    )


class Selection(RootModel[str]):
    root: str = Field(
        None,
        description="The chosen answer alone, when it should differ from the highlight. Absent: the highlight, else secondary.",
        pattern="^#[0-9a-fA-F]{6}$",
        title="Selection",
    )


class InputText(RootModel[str]):
    root: str = Field(
        None,
        description="The colour of the answers typed in the white input boxes (4.5:1 on white). Absent: primary.",
        pattern="^#[0-9a-fA-F]{6}$",
        title="Inputtext",
    )


class ThemeBackground(BaseModel):
    """
    Optional decoration of the page ground.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    type: str | None = Field(None, title="Type")
    gradient_from: str | None = Field(None, alias="gradientFrom", title="Gradientfrom")
    gradient_to: str | None = Field(None, alias="gradientTo", title="Gradientto")
    gradient_angle: int | None = Field(
        None, alias="gradientAngle", title="Gradientangle"
    )
    pattern: str | None = Field(None, title="Pattern")
    image_url: str | None = Field(
        None,
        alias="imageUrl",
        description="Only images from our own storage or Unsplash are shown.",
        title="Imageurl",
    )
    artwork: Literal["marble"] | None = Field(
        None,
        description="Built-in artwork served by the app (marble: a marbled endpaper). It fills the picture half of a welcome or ending page whose layout has one and no image of its own. Absent: none.",
        title="Artwork",
    )


class DraftRetentionDays(RootModel[int]):
    root: int = Field(
        None,
        description="How many days after the last save a draft is kept, 1 to 90; left out, 30.",
        ge=1,
        le=90,
        title="Draftretentiondays",
    )


class Trust(BaseModel):
    """
    What respondents are told about their data, and how answers are
    handled.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    purpose: str | None = Field(None, title="Purpose")
    retention_text: str | None = Field(
        None,
        alias="retentionText",
        description='An internal note stored with the form. It is not shown to respondents: they see only the retention period the form enforces (see "retention").',
        title="Retentiontext",
    )
    privacy_policy_url: str | None = Field(
        None,
        alias="privacyPolicyUrl",
        description="An http(s) URL.",
        title="Privacypolicyurl",
    )
    retention: Retention | None = None
    require_verified_identity: bool | None = Field(
        None, alias="requireVerifiedIdentity", title="Requireverifiedidentity"
    )
    allow_editing_response: bool | None = Field(
        None, alias="allowEditingResponse", title="Alloweditingresponse"
    )
    show_submission_number: bool | None = Field(
        None, alias="showSubmissionNumber", title="Showsubmissionnumber"
    )
    allow_save_draft: bool | None = Field(
        None,
        alias="allowSaveDraft",
        description="Let respondents save a draft and continue later (off by default). Drafts are encrypted, kept apart from the responses and deleted after draftRetentionDays.",
        title="Allowsavedraft",
    )
    draft_retention_days: DraftRetentionDays | None = Field(
        None,
        alias="draftRetentionDays",
        description="How many days after the last save a draft is kept, 1 to 90; left out, 30.",
        title="Draftretentiondays",
    )
    show_review_page: bool | None = Field(
        None,
        alias="showReviewPage",
        description="Respondents see their answers on a page of their own, with a link back to each page, before they send them.",
        title="Showreviewpage",
    )


class MinLength(RootModel[int]):
    root: int = Field(None, ge=0, title="Minlength")


class MaxLength(RootModel[int]):
    root: int = Field(None, ge=0, title="Maxlength")


class Pattern(RootModel[str]):
    root: str = Field(
        None,
        description="A regular expression the text answer must match.",
        max_length=200,
        title="Pattern",
    )


class MinChoices(RootModel[int]):
    root: int = Field(None, ge=0, title="Minchoices")


class MaxChoices(RootModel[int]):
    root: int = Field(None, ge=0, title="Maxchoices")


class Validations(BaseModel):
    """
    Answer constraints. Lengths apply to text answers, values to numbers,
    choices to multiple-selection questions.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    required: bool | None = Field(None, title="Required")
    min_length: MinLength | None = Field(None, alias="minLength", title="Minlength")
    max_length: MaxLength | None = Field(None, alias="maxLength", title="Maxlength")
    min_value: float | None = Field(None, alias="minValue", title="Minvalue")
    max_value: float | None = Field(None, alias="maxValue", title="Maxvalue")
    pattern: Pattern | None = Field(
        None,
        description="A regular expression the text answer must match.",
        title="Pattern",
    )
    min_choices: MinChoices | None = Field(None, alias="minChoices", title="Minchoices")
    max_choices: MaxChoices | None = Field(None, alias="maxChoices", title="Maxchoices")


class WelcomePage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    title: str | None = Field(None, title="Title")
    description: str | None = Field(None, title="Description")
    layout: Layout | None = None
    image_url: str | None = Field(None, alias="imageUrl", title="Imageurl")
    button_text: str | None = Field(None, alias="buttonText", title="Buttontext")


class Choice(BaseModel):
    """
    One option of a choice question. Logic conditions compare with
    ``value``.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    id: str | None = Field(None, title="Id")
    value: str | None = Field(None, title="Value")
    label: str | None = Field(None, title="Label")
    attachment: Attachment | None = None
    logic: Logic | None = Field(
        None,
        description="Offer this option only (SHOW) or unless (HIDE) its conditions hold, at most 20. The conditions read earlier questions of the form. An answer that selects an option that is not offered is refused.",
    )


class Ending(BaseModel):
    """
    A page shown after submitting. A page jump may choose one by its
    ``id``; a plain submit shows the default ending (the one with
    ``isDefault``, else the first).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    id: Id | None = Field(
        None,
        description="Stable id that page jumps name. Given when left out.",
        title="Id",
    )
    name: Name | None = Field(
        None,
        description="Short internal name, e.g. Eligible. Respondents never see it.",
        title="Name",
    )
    is_default: bool | None = Field(
        None,
        alias="isDefault",
        description="Shown after a plain submit. At most one ending.",
        title="Isdefault",
    )
    title: Title | None = Field(None, title="Title")
    message: Message | None = Field(None, title="Message")
    button_text: ButtonText | None = Field(None, alias="buttonText", title="Buttontext")
    button_link: str | None = Field(
        None, alias="buttonLink", description="An http(s) URL.", title="Buttonlink"
    )
    layout: Layout | None = None
    image_url: str | None = Field(None, alias="imageUrl", title="Imageurl")


class OptionFilter(BaseModel):
    """
    Filter a choice question's options by an earlier choice question's
    answer: the options offered are those the chosen options of ``fieldId``
    map to (the union over a multiple choice's selection). Without an answer
    to it (or with only "Other" text) nothing is filtered; a chosen option
    with no entry offers nothing.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    field_id: str = Field(..., alias="fieldId", min_length=1, title="Fieldid")
    mapping: list[OptionFilterEntry] | None = Field(
        None, max_length=2000, title="Mapping"
    )


class Rule(BaseModel):
    """
    A field rule: while ``when`` holds, ``then`` applies. A field's rules
    apply in order; for each property the last active rule wins
    (``required`` starts from ``validations.required``). Rules never show or
    hide a question (that is ``logic``).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    id: str = Field(
        ...,
        description="Unique within the form.",
        pattern="^[A-Za-z0-9_-]{1,64}$",
        title="Id",
    )
    when: RuleWhen
    then: RuleThen


class Theme(BaseModel):
    """
    Colours and style of the form (or of one page, as an override).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    title: str = Field(..., title="Title")
    primary: str = Field(..., title="Primary")
    secondary: str = Field(..., title="Secondary")
    tertiary: str = Field(..., title="Tertiary")
    accent: str = Field(..., title="Accent")
    background: ThemeBackground | None = None
    style: str | None = Field(
        None, description="e.g. classic, sheet, studio, leaflet", title="Style"
    )
    title_font: (
        Literal[
            "public-sans",
            "atkinson-next",
            "archivo",
            "besley",
            "rubik",
            "atkinson-mono",
        ]
        | None
    ) = Field(
        None,
        alias="titleFont",
        description="Face of titles and question labels. Absent: the text face (or the style's own title face).",
        title="Titlefont",
    )
    body_font: (
        Literal[
            "public-sans",
            "atkinson-next",
            "archivo",
            "besley",
            "rubik",
            "atkinson-mono",
        ]
        | None
    ) = Field(
        None,
        alias="bodyFont",
        description="Face of everything else respondents read. Absent: public-sans.",
        title="Bodyfont",
    )
    data_font: (
        Literal[
            "public-sans",
            "atkinson-next",
            "archivo",
            "besley",
            "rubik",
            "atkinson-mono",
        ]
        | None
    ) = Field(
        None,
        alias="dataFont",
        description="Face of data such as the submission number. Absent: the app's mono face.",
        title="Datafont",
    )
    title_width: Literal["normal", "expanded"] | None = Field(
        None,
        alias="titleWidth",
        description="Width of display titles: expanded is 125% on a face with a width axis (archivo).",
        title="Titlewidth",
    )
    radius: Literal["sharp", "soft", "round"] | None = Field(
        None,
        description="Corners of fields, option cards and buttons: sharp 0, soft 6px, round 16px. Absent: the style's own.",
        title="Radius",
    )
    button_style: Literal["filled", "outlined", "pill"] | None = Field(
        None, alias="buttonStyle", description="Absent: filled.", title="Buttonstyle"
    )
    highlight: Highlight | None = Field(
        None,
        description="The chosen answer, the 'why we ask' and 'optional' notes and, where it reads, the focus ring. Absent: secondary.",
        title="Highlight",
    )
    selection: Selection | None = Field(
        None,
        description="The chosen answer alone, when it should differ from the highlight. Absent: the highlight, else secondary.",
        title="Selection",
    )
    input_text: InputText | None = Field(
        None,
        alias="inputText",
        description="The colour of the answers typed in the white input boxes (4.5:1 on white). Absent: primary.",
        title="Inputtext",
    )


class Endings(RootModel[list[Ending]]):
    root: list[Ending] = Field(
        None, description="At most 20 endings.", max_length=20, title="Endings"
    )


class Rules(RootModel[list[Rule]]):
    root: list[Rule] = Field(
        None,
        description="At most 8 rules per question and 100 per form (see Rule).",
        max_length=8,
        title="Rules",
    )


class FormField(BaseModel):
    """
    A question or content block on a page (or inside a group).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    id: str = Field(..., min_length=1, title="Id")
    type: (
        Literal[
            "date",
            "time",
            "day",
            "currency",
            "date_range",
            "tags",
            "address",
            "signature",
            "short_text",
            "long_text",
            "multiple_choice",
            "rating",
            "dropdown",
            "matrix",
            "tabular_input",
            "file_upload",
            "group",
            "email",
            "calculated",
            "text",
            "yes_no",
            "url",
            "linear_rating",
            "phone_number",
            "number",
            "VIDEO_CONTENT",
            "IMAGE_CONTENT",
        ]
        | Literal[
            "opinion_scale",
            "ranking",
            "payment",
            "statement",
            "page_break",
            "hidden",
            "conditional",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "p",
            "strong",
            "divider",
            "markdown",
            "input_short_text",
            "input_long_text",
            "input_markdown",
            "input_multiple_choice",
            "input_multiselect",
            "input_checkboxes",
            "input_email",
            "input_number",
            "input_phone_number",
            "input_link",
            "input_date",
            "input_time",
            "input_date_range",
            "input_time_range",
            "input_datetime_range",
            "input_dropdown",
            "input_rating",
            "input_linear_scale",
            "input_template_button",
            "input_file_upload",
            "input_ranking",
            "input_matrix",
            "date_input",
            "email_input",
            "number_input",
            "short_text_input",
            "long_text_input",
            "multiple_choice_input",
            "ranking_input",
            "rating_input",
            "drop_down_input",
            "media_input",
            "matrix_row_input",
        ]
    ) = Field(..., description="A question or content block type.", title="FieldType")
    title: str | dict[str, Any] | None = Field(
        None,
        description="Plain text, or a rich-text document (which may pipe answers and hidden fields).",
        title="Title",
    )
    description: str | None = Field(None, title="Description")
    value: str | None = Field(None, title="Value")
    image_url: str | None = Field(None, alias="imageUrl", title="Imageurl")
    attachment: Attachment | None = None
    internal: bool | None = Field(
        None,
        description="For office use only: never shown to respondents, filled in by staff on each submission.",
        title="Internal",
    )
    validations: Validations | None = None
    placeholder: str | None = Field(None, title="Placeholder")
    choices: list[Choice] | None = Field(None, title="Choices")
    allow_multiple_selection: bool | None = Field(
        None, alias="allowMultipleSelection", title="Allowmultipleselection"
    )
    allow_other_choice: bool | None = Field(
        None, alias="allowOtherChoice", title="Allowotherchoice"
    )
    steps: int | None = Field(None, title="Steps")
    start_from: int | None = Field(None, alias="startFrom", title="Startfrom")
    rating_shape: str | None = Field(None, alias="ratingShape", title="Ratingshape")
    hide_marks: bool | None = Field(None, alias="hideMarks", title="Hidemarks")
    labels: dict[str, str] | None = Field(None, title="Labels")
    date_format: str | None = Field(None, alias="dateFormat", title="Dateformat")
    row_titles: list[str] | None = Field(None, alias="rowTitles", title="Rowtitles")
    column_titles: list[str] | None = Field(
        None, alias="columnTitles", title="Columntitles"
    )
    tabular_value: list[list[str]] | None = Field(
        None, alias="tabularValue", title="Tabularvalue"
    )
    col_span: ColSpan | None = Field(
        None,
        alias="colSpan",
        description="Width on a 12-column grid (12 = full row).",
        title="Colspan",
    )
    label: Label | None = Field(
        None, description="Short label shown with a date picker.", title="Label"
    )
    date_rules: DateRules | None = Field(
        None,
        alias="dateRules",
        description="Constraints on a date or day question's answer.",
        title="Daterules",
    )
    min_time: MinTime | None = Field(
        None,
        alias="minTime",
        description="A time question: the earliest time that can be answered (HH:MM, 24-hour).",
        title="Mintime",
    )
    max_time: MaxTime | None = Field(
        None,
        alias="maxTime",
        description="A time question: the latest time that can be answered (HH:MM, 24-hour).",
        title="Maxtime",
    )
    currencies: Currencies | None = Field(
        None,
        description="A currency question: the ISO 4217 codes respondents may pick (the first is the default). Amounts are answered with min/max in validations.",
        title="Currencies",
    )
    countries: Countries | None = Field(
        None,
        description="An address question: the ISO 3166-1 alpha-2 codes of the countries respondents may give (default: NL only).",
        title="Countries",
    )
    address_lookup: bool | None = Field(
        None,
        alias="addressLookup",
        description="An address question: fill in street and city from a Dutch postcode and house number while the server offers it (default: yes).",
        title="Addresslookup",
    )
    why_we_ask: WhyWeAsk | None = Field(None, alias="whyWeAsk", title="Whyweask")
    logic: Logic | None = None
    option_filter: OptionFilter | None = Field(
        None,
        alias="optionFilter",
        description="A choice question's options filtered by an earlier choice question's answer (see OptionFilter).",
    )
    option_source: OptionSource | None = Field(
        None,
        alias="optionSource",
        description="A dropdown or multiple choice question's options taken from a workspace list or from another form's answers instead of choices (see OptionSource).",
    )
    share_as_choices: bool | None = Field(
        None,
        alias="shareAsChoices",
        description="A short text, dropdown or multiple choice question: its answers may be shown as choices in other forms of the same workspace (an optionSource of kind form_answers). Off unless true. Respondents are told next to the question; only answers given while a version with it on was filled are ever offered.",
        title="Shareaschoices",
    )
    rules: Rules | None = Field(
        None,
        description="At most 8 rules per question and 100 per form (see Rule).",
        title="Rules",
    )
    expression: Any = Field(
        None,
        description='A calculated field\'s formula as an expressions-v1 syntax tree (docs/spec/expressions-v1.md), e.g. {"+": [{"var": "<field id>"}, 1]}. Variables are question ids, \'<group id>.<question id>\' for a repeating group\'s question, and hidden-field names.',
        title="Expression",
    )
    format: CalculationFormat | None = None
    hidden_from_respondents: bool | None = Field(
        None,
        alias="hiddenFromRespondents",
        description="A calculated field that is computed and stored but never shown to respondents.",
        title="Hiddenfromrespondents",
    )
    unanswered_as_zero: bool | None = Field(
        None,
        alias="unansweredAsZero",
        description="A calculated field: unanswered questions it uses count as 0 (default: on, unless the format is text).",
        title="Unansweredaszero",
    )
    repeat: Repeat | None = None
    fields: list[FormField] | None = Field(
        None, description="The questions of a group.", title="Fields"
    )


class Page(BaseModel):
    """
    A page of questions, in the order respondents see them.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    id: str = Field(..., min_length=1, title="Id")
    section_title: SectionTitle | None = Field(
        None, alias="sectionTitle", title="Sectiontitle"
    )
    layout: Layout | None = None
    image_url: str | None = Field(None, alias="imageUrl", title="Imageurl")
    theme: Theme | None = None
    show_question_numbers: bool | None = Field(
        None, alias="showQuestionNumbers", title="Showquestionnumbers"
    )
    position: Position | None = None
    jumps: list[PageJump] | None = Field(None, title="Jumps")
    fields: list[FormField] | None = Field(None, title="Fields")


class FormSpec(BaseModel):
    """
    A form, as its creator controls it.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    spec_version: Literal["1"] = Field(..., alias="specVersion", title="Specversion")
    title: str | None = Field(None, title="Title")
    description: str | None = Field(None, title="Description")
    language: (
        Literal["nl", "en", "de", "fr", "es", "it", "pt", "pl", "da", "sv", "nb", "fi"]
        | None
    ) = Field(
        None,
        description="The language the form's own text (title, questions, choices) is written in, as a short BCP 47 tag. Respondent pages mark that text with it for screen readers and browsers. When a document that replaces a form leaves it out, the form keeps its language; null clears it.",
        title="Language",
    )
    welcome_page: WelcomePage | None = Field(None, alias="welcomePage")
    pages: list[Page] | None = Field(
        None,
        description="At most 200 pages, with at most 2000 fields in all (group questions included).",
        max_length=200,
        title="Pages",
    )
    endings: Endings | None = Field(
        None, description="At most 20 endings.", title="Endings"
    )
    theme: Theme | None = None
    hidden_fields: list[str] | None = Field(
        None,
        alias="hiddenFields",
        description="URL parameter names captured with each response (names only, never values).",
        title="Hiddenfields",
    )
    logo: Logo | None = None
    trust: Trust | None = None


FormField.model_rebuild()

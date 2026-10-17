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
    root: list[DateRule] = Field(None, max_length=5, title="Daterules")


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


class SectionTitle(RootModel[str]):
    root: str = Field(None, max_length=120, title="Sectiontitle")


class PageJump(BaseModel):
    """
    After this page, go to ``target`` (a page id, or "__SUBMIT__" to
    end the form) when the conditions match. The first matching jump wins;
    no match goes to the next page.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    operator: Literal["AND", "OR"] | None = Field(None, title="Operator")
    conditions: list[Condition] | None = Field(None, title="Conditions")
    target: str | None = Field(None, title="Target")


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
        None, alias="retentionText", title="Retentiontext"
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


class MinLength(RootModel[int]):
    root: int = Field(None, ge=0, title="Minlength")


class MaxLength(RootModel[int]):
    root: int = Field(None, ge=0, title="Maxlength")


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
    pattern: str | None = Field(
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


class Ending(BaseModel):
    """
    A page shown after submitting.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
    title: str | None = Field(None, title="Title")
    message: str | None = Field(None, title="Message")
    button_text: str | None = Field(None, alias="buttonText", title="Buttontext")
    button_link: str | None = Field(
        None, alias="buttonLink", description="An http(s) URL.", title="Buttonlink"
    )
    layout: Layout | None = None
    image_url: str | None = Field(None, alias="imageUrl", title="Imageurl")


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
            "calculated",
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
    date_rules: DateRules | None = Field(None, alias="dateRules", title="Daterules")
    why_we_ask: WhyWeAsk | None = Field(None, alias="whyWeAsk", title="Whyweask")
    logic: Logic | None = None
    repeat: Repeat | None = None
    fields: list[FormField] | None = Field(
        None, description="The questions of a group.", title="Fields"
    )


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
    welcome_page: WelcomePage | None = Field(None, alias="welcomePage")
    pages: list[Page] | None = Field(
        None,
        description="At most 200 pages, with at most 2000 fields in all (group questions included).",
        max_length=200,
        title="Pages",
    )
    endings: list[Ending] | None = Field(None, title="Endings")
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

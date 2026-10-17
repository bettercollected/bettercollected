/* Generated from docs/spec/form-spec-v1.schema.json by scripts/generate.mjs. Do not edit. */

/**
 * How a page, the welcome page or an ending is laid out.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Layout".
 */
export type Layout =
  | "TWO_COLUMN_IMAGE_LEFT"
  | "TWO_COLUMN_IMAGE_RIGHT"
  | "SINGLE_COLUMN_IMAGE_BACKGROUND"
  | "SINGLE_COLUMN_NO_BACKGROUND"
  | "SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN";

/**
 * A form, as its creator controls it.
 */
export interface FormSpec {
  specVersion: "1";
  title?: string | null;
  description?: string | null;
  welcomePage?: WelcomePage | null;
  /**
   * At most 200 pages, with at most 2000 fields in all (group questions included).
   *
   * @maxItems 200
   */
  pages?: Page[];
  endings?: Ending[] | null;
  theme?: Theme | null;
  /**
   * URL parameter names captured with each response (names only, never values).
   */
  hiddenFields?: string[] | null;
  logo?: Logo | null;
  trust?: Trust | null;
}
/**
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "WelcomePage".
 */
export interface WelcomePage {
  title?: string | null;
  description?: string | null;
  layout?: Layout | null;
  imageUrl?: string | null;
  buttonText?: string | null;
}
/**
 * A page of questions, in the order respondents see them.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Page".
 */
export interface Page {
  id: string;
  sectionTitle?: string | null;
  layout?: Layout | null;
  imageUrl?: string | null;
  theme?: Theme | null;
  showQuestionNumbers?: boolean | null;
  position?: Position | null;
  jumps?: PageJump[] | null;
  fields?: FormField[];
}
/**
 * Colours and style of the form (or of one page, as an override).
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Theme".
 */
export interface Theme {
  title: string;
  primary: string;
  secondary: string;
  tertiary: string;
  accent: string;
  background?: ThemeBackground | null;
  /**
   * e.g. classic, sheet, studio, leaflet
   */
  style?: string | null;
}
/**
 * Optional decoration of the page ground.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "ThemeBackground".
 */
export interface ThemeBackground {
  type?: string | null;
  gradientFrom?: string | null;
  gradientTo?: string | null;
  gradientAngle?: number | null;
  pattern?: string | null;
  /**
   * Only images from our own storage or Unsplash are shown.
   */
  imageUrl?: string | null;
}
/**
 * Where a page sits on the flow view's canvas (cosmetic).
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Position".
 */
export interface Position {
  x?: number | null;
  y?: number | null;
}
/**
 * After this page, go to ``target`` (a page id, or "__SUBMIT__" to
 * end the form) when the conditions match. The first matching jump wins;
 * no match goes to the next page.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "PageJump".
 */
export interface PageJump {
  operator?: ("AND" | "OR") | null;
  conditions?: Condition[] | null;
  target?: string | null;
}
/**
 * One condition of a visibility rule or a page jump: the answer of
 * ``fieldId`` compared with ``value`` (a choice's value, "Yes"/"No" for a
 * yes/no question). On a repeating group, ``groupMode`` COUNT compares
 * the number of items; ANY / ALL test ``childFieldId`` in the items.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Condition".
 */
export interface Condition {
  fieldId?: string | null;
  /**
   * Type of the source question (filled in by the editor).
   */
  fieldType?: string | null;
  comparison?:
    | (
        | "IS_EMPTY"
        | "IS_NOT_EMPTY"
        | "IS_EQUAL"
        | "IS_NOT_EQUAL"
        | "CONTAINS"
        | "DOES_NOT_CONTAIN"
        | "LESS_THAN"
        | "LESS_THAN_EQUAL"
        | "GREATER_THAN"
        | "GREATER_THAN_EQUAL"
        | "STARTS_WITH"
        | "ENDS_WITH"
      )
    | null;
  value?: unknown;
  groupMode?: ("COUNT" | "ANY" | "ALL") | null;
  childFieldId?: string | null;
  childFieldType?: string | null;
}
/**
 * A question or content block on a page (or inside a group).
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "FormField".
 */
export interface FormField {
  id: string;
  /**
   * A question or content block type.
   */
  type:
    | (
        | "date"
        | "short_text"
        | "long_text"
        | "multiple_choice"
        | "rating"
        | "dropdown"
        | "matrix"
        | "tabular_input"
        | "file_upload"
        | "group"
        | "email"
        | "calculated"
        | "text"
        | "yes_no"
        | "url"
        | "linear_rating"
        | "phone_number"
        | "number"
        | "VIDEO_CONTENT"
        | "IMAGE_CONTENT"
      )
    | (
        | "opinion_scale"
        | "ranking"
        | "payment"
        | "statement"
        | "page_break"
        | "hidden"
        | "conditional"
        | "h1"
        | "h2"
        | "h3"
        | "h4"
        | "h5"
        | "p"
        | "strong"
        | "divider"
        | "markdown"
        | "input_short_text"
        | "input_long_text"
        | "input_markdown"
        | "input_multiple_choice"
        | "input_multiselect"
        | "input_checkboxes"
        | "input_email"
        | "input_number"
        | "input_phone_number"
        | "input_link"
        | "input_date"
        | "input_time"
        | "input_date_range"
        | "input_time_range"
        | "input_datetime_range"
        | "input_dropdown"
        | "input_rating"
        | "input_linear_scale"
        | "input_template_button"
        | "input_file_upload"
        | "input_ranking"
        | "input_matrix"
        | "date_input"
        | "email_input"
        | "number_input"
        | "short_text_input"
        | "long_text_input"
        | "multiple_choice_input"
        | "ranking_input"
        | "rating_input"
        | "drop_down_input"
        | "media_input"
        | "matrix_row_input"
      );
  /**
   * Plain text, or a rich-text document (which may pipe answers and hidden fields).
   */
  title?:
    | string
    | {
        [k: string]: unknown;
      }
    | null;
  description?: string | null;
  value?: string | null;
  imageUrl?: string | null;
  attachment?: Attachment | null;
  /**
   * For office use only: never shown to respondents, filled in by staff on each submission.
   */
  internal?: boolean | null;
  validations?: Validations | null;
  placeholder?: string | null;
  choices?: Choice[] | null;
  allowMultipleSelection?: boolean | null;
  allowOtherChoice?: boolean | null;
  steps?: number | null;
  startFrom?: number | null;
  ratingShape?: string | null;
  hideMarks?: boolean | null;
  labels?: {
    [k: string]: string;
  } | null;
  dateFormat?: string | null;
  rowTitles?: string[] | null;
  columnTitles?: string[] | null;
  tabularValue?: string[][] | null;
  /**
   * Width on a 12-column grid (12 = full row).
   */
  colSpan?: number | null;
  /**
   * Short label shown with a date picker.
   */
  label?: string | null;
  dateRules?:
    | []
    | [DateRule]
    | [DateRule, DateRule]
    | [DateRule, DateRule, DateRule]
    | [DateRule, DateRule, DateRule, DateRule]
    | [DateRule, DateRule, DateRule, DateRule, DateRule]
    | null;
  whyWeAsk?: string | null;
  logic?: Logic | null;
  expression?: unknown;
  format?: CalculationFormat | null;
  /**
   * A calculated field that is computed and stored but never shown to respondents.
   */
  hiddenFromRespondents?: boolean | null;
  repeat?: Repeat | null;
  /**
   * The questions of a group.
   */
  fields?: FormField[] | null;
}
/**
 * An image or video shown with a question or a choice.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Attachment".
 */
export interface Attachment {
  type?: ("image" | "video") | null;
  href?: string | null;
  scale?: number | null;
  description?: string | null;
  embedProvider?: ("youtube" | "vimeo" | "no_embed") | null;
}
/**
 * Answer constraints. Lengths apply to text answers, values to numbers,
 * choices to multiple-selection questions.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Validations".
 */
export interface Validations {
  required?: boolean | null;
  minLength?: number | null;
  maxLength?: number | null;
  minValue?: number | null;
  maxValue?: number | null;
  /**
   * A regular expression the text answer must match.
   */
  pattern?: string | null;
  minChoices?: number | null;
  maxChoices?: number | null;
}
/**
 * One option of a choice question. Logic conditions compare with
 * ``value``.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Choice".
 */
export interface Choice {
  id?: string | null;
  value?: string | null;
  label?: string | null;
  attachment?: Attachment | null;
}
/**
 * The chosen date must be ``comparison`` a fixed ``date`` (YYYY-MM-DD),
 * today, or the answer of another date question (``fieldId``).
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "DateRule".
 */
export interface DateRule {
  comparison: "before" | "after" | "on_or_before" | "on_or_after";
  target: "date" | "today" | "field";
  date?: string | null;
  fieldId?: string | null;
}
/**
 * Show or hide this question when its conditions match (operator:
 * AND = all, OR = any; AND when absent).
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Logic".
 */
export interface Logic {
  action?: ("SHOW" | "HIDE") | null;
  operator?: ("AND" | "OR") | null;
  conditions?: Condition[] | null;
}
/**
 * How a calculated field shows its value (display only; the stored
 * value is the computed one).
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "CalculationFormat".
 */
export interface CalculationFormat {
  /**
   * number (default), currency, percent (0.25 shows as 25%) or text.
   */
  style?: ("number" | "currency" | "percent" | "text") | null;
  decimals?: number | null;
  /**
   * ISO 4217 code; EUR by default.
   */
  currency?: string | null;
}
/**
 * Makes a group repeatable: its questions are answered once per item.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Repeat".
 */
export interface Repeat {
  minItems?: number | null;
  maxItems?: number | null;
  itemLabel?: string | null;
  itemTitle?: string | null;
  exportLayout?: ("columns" | "rows") | null;
}
/**
 * A page shown after submitting.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Ending".
 */
export interface Ending {
  title?: string | null;
  message?: string | null;
  buttonText?: string | null;
  /**
   * An http(s) URL.
   */
  buttonLink?: string | null;
  layout?: Layout | null;
  imageUrl?: string | null;
}
/**
 * The organisation logo at the top of every respondent page.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Logo".
 */
export interface Logo {
  /**
   * Set by uploading a logo; ignored when a document is written.
   */
  url?: string | null;
  position?: ("auto" | "left" | "center") | null;
  alt?: string | null;
  useWorkspaceLogo?: boolean | null;
}
/**
 * What respondents are told about their data, and how answers are
 * handled.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Trust".
 */
export interface Trust {
  purpose?: string | null;
  retentionText?: string | null;
  /**
   * An http(s) URL.
   */
  privacyPolicyUrl?: string | null;
  retention?: Retention | null;
  requireVerifiedIdentity?: boolean | null;
  allowEditingResponse?: boolean | null;
  showSubmissionNumber?: boolean | null;
}
/**
 * How long answers are kept: a number of days, until a date
 * (YYYY-MM-DD), or forever.
 *
 * This interface was referenced by `FormSpec`'s JSON-Schema
 * via the `definition` "Retention".
 */
export interface Retention {
  type: "days" | "date" | "forever";
  value?: number | string | null;
}

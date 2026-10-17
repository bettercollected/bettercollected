/**
 * Form operations: the typed edits the ops engine applies to a form document.
 *
 * Hand-written to match the backend models in
 * `backend/app/services/ai/ops.py` (camelCase, as the backend's alias
 * generator writes them). The generated types from the shared ops schema
 * replace these later; keep the two in step until then.
 *
 * The document is the builder's form shape (`StandardFormDto`): pages are
 * `slide` fields in `fields`, their questions in `properties.fields`, and the
 * questions of a repeating group in the group's `properties.fields`.
 */
import type { FormTheme } from '@app/constants/theme';
import type { StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';

export type FormDoc = StandardFormDto;
export type FormField = StandardFormFieldDto;
/** A question title: plain text, or the builder's rich-text JSON. */
export type FieldTitle = string | Record<string, any>;

// ---------------------------------------------------------------------------
// Building blocks
// ---------------------------------------------------------------------------

/** What an op supplies to create a question (backend NewFieldSpec). */
export interface NewFieldSpec {
    title: string;
    type: string;
    description?: string | null;
    required?: boolean | null;
    placeholder?: string | null;
    choices?: string[] | null;
    steps?: number | null;
    startFrom?: number | null;
    colSpan?: number | null;
    internal?: boolean | null;
    allowMultiple?: boolean | null;
    label?: string | null;
    whyWeAsk?: string | null;
    ref?: string | null;
}

export type DateRuleComparison = 'before' | 'after' | 'on_or_before' | 'on_or_after';
export type DateRuleTarget = 'date' | 'today' | 'field';

export interface DateRuleSpec {
    comparison: DateRuleComparison;
    target: DateRuleTarget;
    date?: string | null;
    fieldId?: string | null;
}

/** Partial update of a question. Absent (or null) = unchanged. */
export interface FieldPatch {
    title?: FieldTitle | null;
    description?: string | null;
    required?: boolean | null;
    placeholder?: string | null;
    choices?: string[] | null;
    steps?: number | null;
    startFrom?: number | null;
    colSpan?: number | null;
    internal?: boolean | null;
    minItems?: number | null;
    maxItems?: number | null;
    itemLabel?: string | null;
    itemTitle?: string | null;
    exportLayout?: 'columns' | 'rows' | null;
    label?: string | null;
    dateRules?: DateRuleSpec[] | null;
    whyWeAsk?: string | null;
}

/** Answer rules. A key that is present (even null) is changed; null clears it. */
export interface FieldValidationPatch {
    required?: boolean | null;
    minLength?: number | null;
    maxLength?: number | null;
    minValue?: number | null;
    maxValue?: number | null;
    minChoices?: number | null;
    maxChoices?: number | null;
    pattern?: string | null;
    preset?: 'digits' | 'letters' | 'alphanumeric' | null;
}

export type Comparison = 'IS_EMPTY' | 'IS_NOT_EMPTY' | 'IS_EQUAL' | 'IS_NOT_EQUAL' | 'CONTAINS' | 'DOES_NOT_CONTAIN' | 'LESS_THAN' | 'LESS_THAN_EQUAL' | 'GREATER_THAN' | 'GREATER_THAN_EQUAL' | 'STARTS_WITH' | 'ENDS_WITH';

export interface LogicConditionSpec {
    fieldId: string;
    comparison: Comparison;
    value?: any;
    groupMode?: 'COUNT' | 'ANY' | 'ALL' | null;
    childFieldId?: string | null;
}

export interface FieldLogicSpec {
    action: 'SHOW' | 'HIDE';
    operator?: 'AND' | 'OR';
    conditions: LogicConditionSpec[];
}

export interface PageJumpSpec {
    operator?: 'AND' | 'OR';
    conditions: LogicConditionSpec[];
    /** A page id, or `__SUBMIT__`. */
    target: string;
}

/** The form settings ops may change (backend FormSettingsPatch). */
export interface FormSettingsPatch {
    purpose?: string | null;
    retentionText?: string | null;
    privacyPolicyUrl?: string | null;
    requireVerifiedIdentity?: boolean | null;
    allowEditingResponse?: boolean | null;
    showSubmissionNumber?: boolean | null;
}

// ---------------------------------------------------------------------------
// Operations shared with the AI and the API
// ---------------------------------------------------------------------------

export interface AddFieldOp {
    op: 'add_field';
    pageId?: string | null;
    groupId?: string | null;
    field: NewFieldSpec;
    afterFieldId?: string | null;
    index?: number | null;
    ref?: string | null;
}

export interface UpdateFieldOp {
    op: 'update_field';
    fieldId: string;
    patch: FieldPatch;
}

export interface AddGroupOp {
    op: 'add_group';
    pageId: string;
    title: string;
    description?: string | null;
    itemLabel?: string;
    minItems?: number;
    maxItems?: number;
    itemTitle?: string | null;
    exportLayout?: 'columns' | 'rows' | null;
    fields?: NewFieldSpec[];
    afterFieldId?: string | null;
    index?: number | null;
    ref?: string | null;
}

export interface RemoveFieldOp {
    op: 'remove_field';
    fieldId: string;
}

export interface MoveFieldOp {
    op: 'move_field';
    fieldId: string;
    toPageId?: string | null;
    toGroupId?: string | null;
    index?: number | null;
}

export interface AddPageOp {
    op: 'add_page';
    index?: number | null;
    fields?: NewFieldSpec[] | null;
    ref?: string | null;
}

export interface RemovePageOp {
    op: 'remove_page';
    pageId: string;
}

export interface MovePageOp {
    op: 'move_page';
    pageId: string;
    index: number;
}

export interface UpdateFormInfoOp {
    op: 'update_form_info';
    title?: string | null;
    description?: string | null;
}

export interface UpdateFormSettingsOp {
    op: 'update_form_settings';
    patch: FormSettingsPatch;
}

export interface SetFieldLogicOp {
    op: 'set_field_logic';
    fieldId: string;
    logic?: FieldLogicSpec | null;
}

export interface SetPageJumpsOp {
    op: 'set_page_jumps';
    pageId: string;
    jumps?: PageJumpSpec[] | null;
}

export interface DuplicatePageOp {
    op: 'duplicate_page';
    pageId: string;
    index?: number | null;
    ref?: string | null;
}

export interface UpdateThemeOp {
    op: 'update_theme';
    theme: FormTheme;
}

export interface SetThemePresetOp {
    op: 'set_theme_preset';
    name: string;
    style?: string | null;
}

export interface SetSectionTitleOp {
    op: 'set_section_title';
    pageId?: string | null;
    pageIndex?: number | null;
    /** Required key: null or '' clears the section title. */
    title?: string | null;
}

export interface SetFieldValidationOp {
    op: 'set_field_validation';
    fieldId: string;
    validation: FieldValidationPatch;
}

export interface SetQuestionNumberingOp {
    op: 'set_question_numbering';
    pageId?: string | null;
    show: boolean;
}

// ---------------------------------------------------------------------------
// Editor operations: lossless, id-addressed edits the builder makes. Not
// offered to the AI or the API.
// ---------------------------------------------------------------------------

/** Insert a complete question (ids kept) on a page at `index`, or into the repeating group `groupId`. */
export interface InsertFieldOp {
    op: 'insert_field';
    pageId?: string | null;
    groupId?: string | null;
    index: number;
    field: FormField;
}

/** Replace the question with `field.id` by `field`, where it is. */
export interface ReplaceFieldOp {
    op: 'replace_field';
    field: FormField;
}

/** Insert a complete page (type `slide`, its questions included, ids kept) at `index` among the question pages. */
export interface InsertPageOp {
    op: 'insert_page';
    index: number;
    page: FormField;
}

/** A page's own settings; a key left out stays, null clears it. */
export interface PagePatch {
    layout?: string | null;
    imageUrl?: string | null;
    theme?: FormTheme | null;
    position?: { x?: number | null; y?: number | null } | null;
    showQuestionNumbers?: boolean | null;
    sectionTitle?: string | null;
}

export interface UpdatePageOp {
    op: 'update_page';
    pageId: string;
    patch: PagePatch;
}

/** The welcome page; a key left out stays, null clears it. */
export interface WelcomePagePatch {
    title?: string | null;
    description?: string | null;
    layout?: string | null;
    imageUrl?: string | null;
    buttonText?: string | null;
}

export interface UpdateWelcomePageOp {
    op: 'update_welcome_page';
    patch: WelcomePagePatch;
}

/** The form's hidden fields (URL parameter names), as a whole; pipes of names no longer listed are removed. */
export interface SetHiddenFieldsOp {
    op: 'set_hidden_fields';
    names: string[];
}

/** The logo's settings (the logo itself only changes by an upload); a key left out stays, null clears it. */
export interface UpdateLogoOp {
    op: 'update_logo';
    position?: 'auto' | 'left' | 'center' | null;
    alt?: string | null;
    useWorkspaceLogo?: boolean | null;
}

export interface EditorChoice {
    id: string;
    value?: string | null;
    ref?: string | null;
    label?: string | null;
    attachment?: Record<string, any> | null;
}

export interface SetChoiceOp {
    op: 'set_choice';
    fieldId: string;
    choiceId: string;
    value?: string | null;
}

/** Add a choice, its id kept, at `index` (default: the end). */
export interface AddChoiceOp {
    op: 'add_choice';
    fieldId: string;
    choice: EditorChoice;
    index?: number | null;
}

export interface RemoveChoiceOp {
    op: 'remove_choice';
    fieldId: string;
    choiceId: string;
}

export interface MoveChoiceOp {
    op: 'move_choice';
    fieldId: string;
    choiceId: string;
    index: number;
}

export type AiFormOp =
    | AddFieldOp
    | AddGroupOp
    | UpdateFieldOp
    | RemoveFieldOp
    | MoveFieldOp
    | AddPageOp
    | RemovePageOp
    | UpdateFormInfoOp
    | UpdateFormSettingsOp
    | SetFieldLogicOp
    | SetPageJumpsOp
    | DuplicatePageOp
    | UpdateThemeOp
    | SetThemePresetOp
    | SetSectionTitleOp
    | MovePageOp
    | SetFieldValidationOp
    | SetQuestionNumberingOp;

export type EditorFormOp = InsertFieldOp | ReplaceFieldOp | InsertPageOp | UpdatePageOp | UpdateWelcomePageOp | SetHiddenFieldsOp | UpdateLogoOp | SetChoiceOp | AddChoiceOp | RemoveChoiceOp | MoveChoiceOp;

export type FormOp = AiFormOp | EditorFormOp;
export type FormOpName = FormOp['op'];

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------

export interface OpResult {
    index: number;
    op: string;
    ok: boolean;
    /** Human-readable: what changed, or why the op failed. */
    message: string;
    /** The id of the page, field or group the op created, if any. */
    createdId?: string;
}

/** The pages, questions and form-level keys a batch changed. */
export interface Touched {
    pages: Set<string>;
    fields: Set<string>;
    /** Top-level form keys other than `fields` (title, theme, settings, ...). */
    form: Set<string>;
}

export interface ApplyOptions {
    /**
     * All or nothing: when any op fails the document comes back unchanged
     * (every op is still tried, so that all errors are reported). Default:
     * partial — failed ops are reported and skipped.
     */
    atomic?: boolean;
    /** Makes the ids of new pages, questions and choices (default: uuid v4). */
    newId?: () => string;
    /**
     * Write applied `update_form_settings` ops into `doc.settings`, as the
     * backend's apply_settings_ops does to the stored settings. Default true;
     * false leaves settings alone, as the backend's form engine does.
     */
    applySettings?: boolean;
    /**
     * Is this address one of our own storage's public images? It depends on
     * the server's storage configuration (backend services/image_urls.py);
     * without it, only Unsplash photos, the built-in images and addresses
     * the form already holds are accepted (see images.ts).
     */
    isStorageImageUrl?: (url: string) => boolean;
    /** Skip building the inverse ops (for previews that never undo). */
    skipInverse?: boolean;
}

export interface ApplyResult {
    doc: FormDoc;
    results: OpResult[];
    /** Ids of every page, question and group the batch created, in order. */
    createdIds: string[];
    /** Ops that turn `doc` back into the document the batch started from. */
    inverse: FormOp[];
    touched: Touched;
}

import { FormTheme, isHexColour } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { PageJump } from '@app/models/types/form-builder-shared';
import { Ending, isJumpEndingMissing, withEndingIds } from '@app/utils/endings';
import { legacyTitleText } from '@app/utils/legacy-title';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import { ContrastIssueKey, themeContrastGuard } from '@app/utils/theme-contrast';

/**
 * Honest defaults a form must meet before it is published. The backend
 * enforces the same rules on every publish (services/publish_checks.py —
 * keep the two in step); the builder checks first so the creator sees what
 * to fix, and where, before anything is sent.
 */

export type PublishProblemCode = 'missing_why_we_ask' | 'required_unanswerable' | 'preset_answer' | 'untitled_question' | 'missing_ending' | 'theme_contrast' | 'needs_review';

export interface PublishProblem {
    code: PublishProblemCode;
    /** The question; for `missing_ending` the page whose jump it is; for `theme_contrast` THEME_PROBLEM_ID. */
    fieldId: string;
    message: string;
    /** `needs_review` only: the id of the import report to look through (nothing of its content). */
    importId?: string | null;
}

/** Most characters a "why we ask this" line may have (backend WHY_WE_ASK_MAX_LENGTH). */
export const WHY_WE_ASK_MAX_LENGTH = 280;

const IDENTIFYING_TYPES: ReadonlyArray<string> = [FieldTypes.EMAIL, FieldTypes.PHONE_NUMBER];
const ID_NUMBER_CANDIDATE_TYPES: ReadonlyArray<string> = [FieldTypes.SHORT_TEXT, FieldTypes.LONG_TEXT, FieldTypes.NUMBER];
// Kept narrow on purpose: whole words, and "ID"/"passport" only with "number".
const ID_NUMBER_TITLE =
    /\b(bsn|burgerservicenummer|sofinummer|sofi-nummer|passport\s*(?:number|no\.?|nr\.?)|paspoortnummer|paspoort\s*(?:nummer|nr\.?)|id[\s-]?(?:number|nummer|nr\.?|no\.?)|identification\s+number|identity\s+(?:card\s+)?number|identiteitsnummer|identiteitskaartnummer|national\s+(?:id|identity|insurance)\s+number|social\s+security\s+number|ssn)(?![\w-])/i;

const DISPLAY_ONLY_TYPES: ReadonlyArray<string> = [FieldTypes.TEXT, FieldTypes.STATEMENT, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT, 'h1', 'h2', 'h3', 'h4', 'h5', 'p', 'strong', 'divider', 'markdown'];
const CHOICE_TYPES: ReadonlyArray<string> = [FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN, FieldTypes.RANKING];
const PRESET_ANSWER_TYPES: ReadonlyArray<string> = [...CHOICE_TYPES, FieldTypes.YES_NO];

export function questionText(field: StandardFormFieldDto): string {
    const title = field?.title;
    const text = typeof title === 'string' ? title : title ? extractTextfromJSON({ ...field, title } as StandardFormFieldDto) : '';
    return (text || '').split(/\s+/).filter(Boolean).join(' ');
}

/**
 * The words of a field's own title, or '' when it has none: no per-type
 * placeholder stands in (an untitled question must be named before
 * publishing). A legacy plain title (`value`) counts (utils/legacy-title.ts).
 */
export function ownTitleText(field: StandardFormFieldDto): string {
    const title = field?.title;
    const walk = (node: any): string => {
        if (!node) return '';
        if (node.type === 'text') return node.text ?? '';
        if (node.type === 'answerPipe') return node.attrs?.label || node.attrs?.pipeKey || '';
        return (node.content ?? []).map(walk).join(' ');
    };
    let text = typeof title === 'string' ? title : title ? walk(title) : '';
    if (!title) text = legacyTitleText(field) ?? '';
    return text.split(/\s+/).filter(Boolean).join(' ');
}

/** Does this question collect an email, a phone number or an ID number? */
export function asksForIdentity(field: StandardFormFieldDto): boolean {
    if (IDENTIFYING_TYPES.includes(field?.type)) return true;
    if (ID_NUMBER_CANDIDATE_TYPES.includes(field?.type)) return ID_NUMBER_TITLE.test(questionText(field));
    return false;
}

function label(field: StandardFormFieldDto): string {
    let text = questionText(field);
    if (text.length > 60) text = text.slice(0, 57).trimEnd() + '...';
    return text ? `"${text}"` : 'A question';
}

const choiceText = (choice: any) => String(choice?.value || choice?.label || '').trim();

/**
 * Does the field's `value` pick one of its own options? Older form formats
 * used `value` as a default answer; today it only holds a legacy title,
 * which names no option.
 */
export function hasPresetAnswer(field: StandardFormFieldDto): boolean {
    if (!PRESET_ANSWER_TYPES.includes(field?.type)) return false;
    const value = String(field?.value ?? '')
        .trim()
        .toLowerCase();
    if (!value) return false;
    const options = (field?.properties?.choices ?? []).map((choice) => choiceText(choice).toLowerCase());
    if (field.type === FieldTypes.YES_NO) options.push('yes', 'no');
    return options.includes(value);
}

function unanswerableReason(field: StandardFormFieldDto): string | null {
    const type = field?.type;
    if (DISPLAY_ONLY_TYPES.includes(type)) return 'it only shows content';
    if (type === FieldTypes.GROUP && !field?.properties?.repeat) return 'it is only a group heading';
    if (CHOICE_TYPES.includes(type) && !(field?.properties?.choices ?? []).some((choice) => choiceText(choice))) return 'it has no options to choose from';
    if (type === FieldTypes.MATRIX) {
        const rows = field?.properties?.fields ?? [];
        if (rows.length && !rows.some((row) => (row?.properties?.choices ?? []).some((choice) => choiceText(choice)))) return 'its grid has no columns to choose from';
    }
    return null;
}

/** Every question of the form: page fields and the questions inside groups, with where they are. */
function questions(slides: Array<StandardFormFieldDto> | undefined): Array<{ field: StandardFormFieldDto; where: string }> {
    const out: Array<{ field: StandardFormFieldDto; where: string }> = [];
    (slides ?? []).forEach((slide, pageIndex) => {
        const fields = slide?.type === FieldTypes.SLIDE ? (slide?.properties?.fields ?? []) : [slide];
        fields.forEach((field, fieldIndex) => {
            out.push({ field, where: `Question ${fieldIndex + 1} on page ${pageIndex + 1}` });
            if (field?.type === FieldTypes.GROUP) {
                (field?.properties?.fields ?? []).forEach((child, childIndex) => out.push({ field: child, where: `Question ${childIndex + 1} of the group on page ${pageIndex + 1}` }));
            }
        });
    });
    return out;
}

/**
 * Everything that keeps this form from being published, in form order.
 * `endings`: the form's endings; when given, a page jump to an ending the
 * form no longer has is a problem too.
 */
export function getPublishProblems(slides: Array<StandardFormFieldDto> | undefined, endings?: Ending[] | null): PublishProblem[] {
    const problems: PublishProblem[] = [];
    questions(slides).forEach(({ field, where }) => {
        if (!field || field.internal) return;
        if (!DISPLAY_ONLY_TYPES.includes(field.type) && !ownTitleText(field)) {
            problems.push({ code: 'untitled_question', fieldId: field.id, message: `${where} has no title. Write the question respondents should answer.` });
        }
        const name = label(field);
        if (hasPresetAnswer(field)) {
            problems.push({ code: 'preset_answer', fieldId: field.id, message: `${name} starts with an answer already chosen. Respondents must choose for themselves: clear the preset answer.` });
        }
        if (field.validations?.required) {
            const reason = unanswerableReason(field);
            if (reason) problems.push({ code: 'required_unanswerable', fieldId: field.id, message: `${name} is required, but ${reason}, so nobody could get past it. Turn off Required or complete the question.` });
        }
        if (asksForIdentity(field) && !field.properties?.whyWeAsk?.trim()) {
            problems.push({ code: 'missing_why_we_ask', fieldId: field.id, message: `${name} asks for personal details. Add a short "Why we ask this" line to the question so respondents know why you need it.` });
        }
    });
    if (endings !== undefined) {
        const known = withEndingIds(endings);
        (slides ?? []).forEach((slide, index) => {
            ((slide?.properties?.jumps as PageJump[] | undefined) ?? []).forEach((jump) => {
                if (isJumpEndingMissing(jump, known)) problems.push({ code: 'missing_ending', fieldId: slide.id, message: `A jump on page ${index + 1} goes to an ending that no longer exists. Choose another ending for it.` });
            });
        });
    }
    return problems;
}

/** The `fieldId` of the theme's problem: it belongs to no question. */
export const THEME_PROBLEM_ID = 'theme';

const CONTRAST_WORDS: Record<ContrastIssueKey, string> = {
    text: 'questions and text on the page',
    answer: 'answers in the input boxes',
    button: 'white text on buttons',
    border: 'input borders',
    action: 'chosen answers and progress'
};

/**
 * The form's theme, when its own colours fail WCAG AA contrast where the
 * respondent form shows them (text 4.5:1, controls 3:1; utils/theme-contrast.ts
 * themeContrastGuard). Every preset passes; a custom or saved palette may
 * not. It stops publishing for every form: respondents can't read it. A
 * theme without its four colours (an old form on the defaults) isn't checked.
 */
export function themeContrastProblems(theme: Partial<FormTheme> | null | undefined): PublishProblem[] {
    if (!theme || !(['primary', 'secondary', 'tertiary', 'accent'] as const).every((role) => isHexColour(theme[role]))) return [];
    const { issues } = themeContrastGuard(theme as FormTheme);
    if (!issues.length) return [];
    const words = issues.map((issue) => CONTRAST_WORDS[issue.key]);
    const list = words.length > 1 ? `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}` : words[0];
    return [{ code: 'theme_contrast', fieldId: THEME_PROBLEM_ID, message: `The theme's colours are hard to read: ${list}. Use the suggested colours on the Design tab, or pick others.` }];
}

/** The problems a refused publish (422 form_not_publishable) carries, if any. */
export function problemsFromPublishError(error: any): PublishProblem[] {
    const body = error?.data ?? error;
    if (body?.code !== 'form_not_publishable' || !Array.isArray(body?.problems)) return [];
    return body.problems.filter((problem: any) => typeof problem?.message === 'string');
}

/** The "this import still needs review" problem among a refusal's problems, if any. */
export function needsReviewProblem(problems: PublishProblem[]): PublishProblem | undefined {
    return problems.find((problem) => problem.code === 'needs_review');
}

/**
 * Which problems stop publishing and which are only recommended. "Why we ask
 * this" is required of forms created under the publish checks
 * (`settings.publishChecksVersion`); forms made before them were published
 * without it and stay publishable, so for them it is a recommendation. The
 * other rules hold for every form (backend `ensure_publishable`).
 */
export function splitPublishProblems(problems: PublishProblem[], publishChecksVersion?: number | null): { blocking: PublishProblem[]; recommended: PublishProblem[] } {
    const requiresReason = !!publishChecksVersion && publishChecksVersion >= 1;
    const recommended = requiresReason ? [] : problems.filter((problem) => problem.code === 'missing_why_we_ask');
    return { blocking: problems.filter((problem) => !recommended.includes(problem)), recommended };
}

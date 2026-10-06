import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

/**
 * Honest defaults a form must meet before it is published. The backend
 * enforces the same rules on every publish (services/publish_checks.py —
 * keep the two in step); the builder checks first so the creator sees what
 * to fix, and where, before anything is sent.
 */

export type PublishProblemCode = 'missing_why_we_ask' | 'required_unanswerable' | 'preset_answer';

export interface PublishProblem {
    code: PublishProblemCode;
    fieldId: string;
    message: string;
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

/** Every question of the form: page fields and the questions inside groups. */
function questions(slides: Array<StandardFormFieldDto> | undefined): StandardFormFieldDto[] {
    const out: StandardFormFieldDto[] = [];
    (slides ?? []).forEach((slide) => {
        const fields = slide?.type === FieldTypes.SLIDE ? (slide?.properties?.fields ?? []) : [slide];
        fields.forEach((field) => {
            out.push(field);
            if (field?.type === FieldTypes.GROUP) out.push(...(field?.properties?.fields ?? []));
        });
    });
    return out;
}

/** Everything that keeps this form from being published, in form order. */
export function getPublishProblems(slides: Array<StandardFormFieldDto> | undefined): PublishProblem[] {
    const problems: PublishProblem[] = [];
    questions(slides).forEach((field) => {
        if (!field || field.internal) return;
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
    return problems;
}

/** The problems a refused publish (422 form_not_publishable) carries, if any. */
export function problemsFromPublishError(error: any): PublishProblem[] {
    const body = error?.data ?? error;
    if (body?.code !== 'form_not_publishable' || !Array.isArray(body?.problems)) return [];
    return body.problems.filter((problem: any) => typeof problem?.message === 'string');
}

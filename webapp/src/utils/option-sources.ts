import type { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldTypes } from '@app/models/dtos/form';

/**
 * Where a dropdown or multiple choice question takes its options from
 * (`properties.optionSource`), instead of `choices`: a workspace list, or the
 * answers to a question of another form of the workspace. The server is
 * authoritative (backend services/option_sources); a respondent's copy of the
 * form carries the `kind` and the parent question only.
 */
export type OptionSource = { kind: 'list'; listId?: string; parentFieldId?: string } | { kind: 'form_answers'; formId?: string; questionId?: string };

/** What a respondent is offered: an id and the text, nothing else. */
export interface SourceOption {
    id: string;
    label: string;
}

export interface SourceOptionsPage {
    items: SourceOption[];
    total: number;
    truncated: boolean;
    /** False when the list or the other form's question is gone. */
    available: boolean;
}

/** The kinds of question that can take options from a source. */
export const SOURCE_CHOICE_TYPES: ReadonlyArray<string> = [FieldTypes.DROP_DOWN, FieldTypes.MULTIPLE_CHOICE];
/** The kinds of question of another form whose answers can become options (never an email, phone, number, address or file). */
export const ANSWER_SOURCE_TYPES: ReadonlyArray<string> = [FieldTypes.SHORT_TEXT, FieldTypes.DROP_DOWN, FieldTypes.MULTIPLE_CHOICE];

/** The most options the server cuts a form's answers to. */
export const ANSWER_OPTIONS_MAX = 1000;

export const hasOptionSource = (field: Pick<StandardFormFieldDto, 'properties'> | undefined | null): boolean => !!field?.properties?.optionSource;

export const isAnswersSource = (source: OptionSource | undefined): source is Extract<OptionSource, { kind: 'form_answers' }> => source?.kind === 'form_answers';

/** The option ids a choice answer holds (one for a single choice, several for a multiple choice). */
export function chosenOptionIds(answer: any): string[] {
    const many = answer?.choices;
    if (many && typeof many === 'object' && Array.isArray(many.values)) return many.values.filter((v: unknown): v is string => typeof v === 'string' && v !== '');
    const one = answer?.choice?.value;
    return typeof one === 'string' && one ? [one] : [];
}

/** `{option id: text}` the answer carries for the options it chose (the server writes it; the page writes it too, for what shows before saving). */
export function answerLabels(answer: any): Record<string, string> {
    const labels: Record<string, string> = {};
    const many = answer?.choices;
    if (many && typeof many === 'object' && many.labels && typeof many.labels === 'object' && !Array.isArray(many.labels)) {
        for (const [id, label] of Object.entries(many.labels)) if (typeof label === 'string' && label) labels[id] = label;
    }
    const one = answer?.choice;
    if (typeof one?.value === 'string' && typeof one?.label === 'string' && one.label) labels[one.value] = one.label;
    return labels;
}

/** The texts of a sourced question's answer, in the order chosen, then an "Other" text as written. Never an id. */
export function sourcedAnswerTexts(answer: any): string[] {
    const labels = answerLabels(answer);
    const texts = chosenOptionIds(answer)
        .map((id) => labels[id])
        .filter((text): text is string => !!text);
    const other = answer?.choices?.other ?? answer?.choice?.other;
    if (typeof other === 'string' && other.trim()) texts.push(other.trim());
    return texts;
}

/** The ids the respondent chose in the question a dependent list depends on (none: nothing is filtered). */
export function parentOptionIds(field: StandardFormFieldDto, answers: Record<string, any> | undefined): string[] {
    const source = field.properties?.optionSource;
    if (source?.kind !== 'list' || !source.parentFieldId) return [];
    return chosenOptionIds(answers?.[source.parentFieldId]);
}

/** A key that changes when the parent's choice changes (an empty string without a parent or an answer). */
export const parentKey = (ids: string[]): string => [...ids].sort().join('\u0000');

/** Can the question's answers be shared as choices at all: a page-level text, dropdown or multiple choice question that is not internal and has no source of its own? */
export const canShareAsChoices = (question: StandardFormFieldDto | undefined | null): boolean => !!question && !question.internal && ANSWER_SOURCE_TYPES.includes(String(question.type)) && !hasOptionSource(question);

/** The questions a creator can pick as the source of another form's answers: those of its pages that can share and whose creator turned sharing on (`shareAsChoices`). */
export function answerSourceQuestions(form: { fields?: StandardFormFieldDto[] } | undefined | null): StandardFormFieldDto[] {
    return pageQuestions(form).filter((question) => canShareAsChoices(question) && question.properties?.shareAsChoices === true);
}

/** The questions a form could share (the creator may turn it on), whether or not they do yet. */
export const shareableQuestions = (form: { fields?: StandardFormFieldDto[] } | undefined | null): StandardFormFieldDto[] => pageQuestions(form).filter(canShareAsChoices);

function pageQuestions(form: { fields?: StandardFormFieldDto[] } | undefined | null): StandardFormFieldDto[] {
    return (form?.fields ?? []).flatMap((slide) => slide?.properties?.fields ?? []);
}

/** Does a form share any answers as choices (its privacy panel says so)? */
export const formSharesAnswers = (fields: StandardFormFieldDto[] | undefined | null): boolean => pageQuestions({ fields: fields ?? [] }).some((question) => question.properties?.shareAsChoices === true && canShareAsChoices(question));

/** The earlier dropdown and multiple choice questions a dependent list can follow (page level, not the question itself). */
export function parentCandidates(slides: StandardFormFieldDto[] | undefined, fieldId: string): StandardFormFieldDto[] {
    const found: StandardFormFieldDto[] = [];
    for (const slide of slides ?? []) {
        for (const question of slide?.properties?.fields ?? []) {
            if (question.id === fieldId) return found;
            if (!question.internal && SOURCE_CHOICE_TYPES.includes(String(question.type))) found.push(question);
        }
    }
    return found;
}

/** Whether a condition on a question with a source may use this comparison: only "is it answered". */
export const SOURCE_COMPARISONS: ReadonlyArray<string> = ['IS_EMPTY', 'IS_NOT_EMPTY', 'is_empty', 'is_not_empty'];

/** The texts of the options chosen in the question a dependent list follows (the builder's preview filters by them): a static option's text, or the text stored with the answer of a sourced one. */
export function parentLabelsOf(field: StandardFormFieldDto, answers: Record<string, any> | undefined, slides: StandardFormFieldDto[] | undefined): string[] {
    const source = field.properties?.optionSource;
    if (source?.kind !== 'list' || !source.parentFieldId) return [];
    const parent = (slides ?? []).flatMap((slide) => slide?.properties?.fields ?? []).find((question) => question.id === source.parentFieldId);
    const answer = answers?.[source.parentFieldId];
    const stored = answerLabels(answer);
    return chosenOptionIds(answer)
        .map((id) => {
            const choice = (parent?.properties?.choices ?? []).find((option) => option.id === id);
            return choice?.value || choice?.label || stored[id];
        })
        .filter((text): text is string => !!text);
}

/**
 * The share notice token to send back with a submission, or null. The backend hands one out with the published form
 * while a question shares its answers; it goes back only when this page shows that notice (a question with
 * `shareAsChoices` on), so an answer is offered to other forms only when the notice was part of the page.
 */
export function shareNoticeTokenToSend(form?: { fields?: StandardFormFieldDto[]; shareNoticeToken?: string | null } | null): string | null {
    if (!form?.fields || !form.fields.some((slide) => (slide?.properties?.fields ?? []).some((question) => question?.properties?.shareAsChoices === true))) return null;
    const token = form.shareNoticeToken;
    return typeof token === 'string' && token.length > 0 ? token : null;
}

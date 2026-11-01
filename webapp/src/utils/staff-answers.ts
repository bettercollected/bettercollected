import { AnswerDto, FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { INTERNAL_CAPABLE_FIELD_TYPES, InternalInputValue, buildInternalAnswer, internalAnswerToInput } from '@app/utils/internal-fields';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

/**
 * Staff edit of a response's answers (docs/response-revisions.md). The editor
 * offers the question types the dashboard already edits for internal fields;
 * every other answerable question is listed as one that cannot be changed
 * here. The server checks every edit like a respondent's own.
 */

/** Types whose empty value is a real answer (an empty text), so they can be cleared. */
const CLEARABLE_TYPES: string[] = [FieldTypes.SHORT_TEXT, FieldTypes.LONG_TEXT];
/** Not questions a respondent answers: nothing to list. */
const NOT_ANSWERABLE: string[] = [FieldTypes.SLIDE, FieldTypes.STATEMENT, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT, FieldTypes.CALCULATED];

function pagesOf(form: Pick<StandardFormDto, 'fields'> | undefined | null): StandardFormFieldDto[] {
    return (form?.fields ?? []).filter((field) => !field.type || field.type === FieldTypes.SLIDE);
}

/** The questions of the form's pages, in order (a group counts as one question). */
export function pageQuestions(form: Pick<StandardFormDto, 'fields'> | undefined | null): StandardFormFieldDto[] {
    return pagesOf(form).flatMap((page) => (page.properties?.fields ?? []) as StandardFormFieldDto[]);
}

/** Questions staff can change here: a type the editor knows, not an internal field (its own panel). */
export function editableQuestions(form: Pick<StandardFormDto, 'fields'> | undefined | null): StandardFormFieldDto[] {
    return pageQuestions(form).filter((field) => !field.internal && INTERNAL_CAPABLE_FIELD_TYPES.includes(field.type as string));
}

/** Answerable questions staff cannot change here (a signature, a file, an address, a group, ...). */
export function lockedQuestions(form: Pick<StandardFormDto, 'fields'> | undefined | null): StandardFormFieldDto[] {
    return pageQuestions(form).filter((field) => !field.internal && !NOT_ANSWERABLE.includes(field.type as string) && !INTERNAL_CAPABLE_FIELD_TYPES.includes(field.type as string));
}

export const questionTitle = (field: StandardFormFieldDto): string => extractTextfromJSON(field)?.trim() || '';

/** Editor values for the stored answers of the editable questions. */
export function inputsFor(fields: StandardFormFieldDto[], answers: Record<string, AnswerDto>): Record<string, InternalInputValue> {
    return Object.fromEntries(fields.map((field) => [field.id, internalAnswerToInput(field, answers?.[field.id])]));
}

const isBlank = (value: InternalInputValue) => value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0);

/**
 * The answer to send for one question, or undefined to leave it as it is. A
 * blank value clears a text answer (an empty text); for any other type an
 * answer cannot be removed (the server only changes answers, as for a
 * respondent), so blank means no change.
 */
export function staffAnswer(field: StandardFormFieldDto, value: InternalInputValue): Record<string, any> | undefined {
    const built = buildInternalAnswer(field, value);
    if (built) return built;
    return isBlank(value) && CLEARABLE_TYPES.includes(field.type as string) ? { field: { id: field.id }, type: 'text', text: '' } : undefined;
}

/** Only the questions whose value differs from what is stored, as answers. */
export function changedAnswers(fields: StandardFormFieldDto[], stored: Record<string, AnswerDto>, values: Record<string, InternalInputValue>): Record<string, Record<string, any>> {
    const changes: Record<string, Record<string, any>> = {};
    for (const field of fields) {
        const next = staffAnswer(field, values[field.id]);
        if (next === undefined) continue;
        const before = staffAnswer(field, internalAnswerToInput(field, stored?.[field.id]));
        if (JSON.stringify(before ?? null) !== JSON.stringify(next)) changes[field.id] = next;
    }
    return changes;
}

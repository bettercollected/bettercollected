import { AnswerDto, FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { getAnswerForField } from '@app/utils/form-builder-block-utils';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

/**
 * Internal ("for office use only") fields.
 *
 * A field with `internal: true` is part of the form definition but is never
 * shown to respondents: workspace members fill it in on each submission
 * afterwards (reference number, reviewer, status…). The backend already strips
 * internal fields from every payload served to non-members; the helpers here
 * keep member-side responder surfaces (preview, a member opening the public
 * link) and the builder's logic pickers consistent with that.
 *
 * Values live in `response.internalAnswers` (same answer shape as respondent
 * answers), never in `response.answers`.
 */

/** Column prefix in the responses table and CSV export. */
export const INTERNAL_COLUMN_PREFIX = 'Internal: ';

/** Field types that can be marked internal and edited from the dashboard. */
export const INTERNAL_CAPABLE_FIELD_TYPES: Array<string> = [
    FieldTypes.SHORT_TEXT,
    FieldTypes.LONG_TEXT,
    FieldTypes.NUMBER,
    FieldTypes.DATE,
    FieldTypes.EMAIL,
    FieldTypes.LINK,
    FieldTypes.PHONE_NUMBER,
    FieldTypes.MULTIPLE_CHOICE,
    FieldTypes.DROP_DOWN,
    FieldTypes.YES_NO
];

export const isInternalField = (field: StandardFormFieldDto | undefined | null): boolean => !!field?.internal;

export const canBeInternal = (field: StandardFormFieldDto | undefined | null): boolean => !!field && INTERNAL_CAPABLE_FIELD_TYPES.includes(field.type);

/** Internal questions of a v2 form, in page/field order. */
export function getInternalFields(form: Pick<StandardFormDto, 'fields'> | undefined | null): StandardFormFieldDto[] {
    const internal: StandardFormFieldDto[] = [];
    (form?.fields ?? []).forEach((slide) => {
        if (slide?.type === FieldTypes.SLIDE) {
            slide?.properties?.fields?.forEach((field) => {
                if (isInternalField(field)) internal.push(field);
            });
        } else if (isInternalField(slide)) {
            internal.push(slide);
        }
    });
    return internal;
}

/**
 * The form as a respondent sees it: internal fields removed, and a page whose
 * fields were all internal removed as a whole (it would be an empty page).
 * Pages that were empty to begin with are kept. Never mutates its input.
 */
export function stripInternalFields<T extends Pick<StandardFormDto, 'fields'>>(form: T): T {
    if (!form?.fields?.length) return form;
    let changed = false;
    const slides: StandardFormFieldDto[] = [];
    form.fields.forEach((slide) => {
        if (isInternalField(slide)) {
            changed = true;
            return;
        }
        const children = slide?.properties?.fields;
        if (slide?.type === FieldTypes.SLIDE && children?.length) {
            const kept = children.filter((field) => !isInternalField(field));
            if (kept.length !== children.length) {
                changed = true;
                if (kept.length === 0) return;
                slides.push({ ...slide, properties: { ...slide.properties, fields: kept } });
                return;
            }
        }
        slides.push(slide);
    });
    return changed ? { ...form, fields: slides } : form;
}

/** Editable value for one internal answer: string, list of choice ids, or yes/no. */
export type InternalInputValue = string | string[] | boolean | undefined;

export function internalAnswerToInput(field: StandardFormFieldDto, answer: AnswerDto | undefined | null): InternalInputValue {
    if (!answer) return field.type === FieldTypes.MULTIPLE_CHOICE && field.properties?.allowMultipleSelection ? [] : undefined;
    switch (field.type) {
        case FieldTypes.NUMBER:
            return answer.number === undefined || answer.number === null ? '' : String(answer.number);
        case FieldTypes.DATE:
            // <input type="date"> wants YYYY-MM-DD; stored dates may carry a time.
            return (answer.date ?? '').slice(0, 10);
        case FieldTypes.EMAIL:
            return answer.email ?? '';
        case FieldTypes.LINK:
            return answer.url ?? '';
        case FieldTypes.PHONE_NUMBER:
            return answer.phone_number ?? answer.phoneNumber ?? '';
        case FieldTypes.YES_NO:
            return typeof answer.boolean === 'boolean' ? answer.boolean : undefined;
        case FieldTypes.MULTIPLE_CHOICE:
        case FieldTypes.DROP_DOWN:
            if (field.properties?.allowMultipleSelection) return answer.choices?.values ?? [];
            return answer.choice?.value ?? '';
        default:
            return answer.text ?? '';
    }
}

const isBlank = (value: InternalInputValue) => value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0);

/**
 * Build the stored answer for an internal field from an editor value, in the
 * same slot the responder uses (so display + CSV reuse `getAnswerForField`).
 * Returns null for an empty value, which clears the answer. Choice values are
 * choice ids, as the v2 responder stores them.
 */
export function buildInternalAnswer(field: StandardFormFieldDto, value: InternalInputValue): Record<string, any> | null {
    if (isBlank(value)) return null;
    const base = { field: { id: field.id } };
    switch (field.type) {
        case FieldTypes.NUMBER: {
            const number = Number(value);
            return Number.isFinite(number) ? { ...base, type: 'number', number } : null;
        }
        case FieldTypes.DATE:
            return { ...base, type: 'date', date: String(value) };
        case FieldTypes.EMAIL:
            return { ...base, type: 'email', email: String(value) };
        case FieldTypes.LINK:
            return { ...base, type: 'url', url: String(value) };
        case FieldTypes.PHONE_NUMBER:
            return { ...base, type: 'phone_number', phone_number: String(value) };
        case FieldTypes.YES_NO:
            return { ...base, type: 'boolean', boolean: value === true };
        case FieldTypes.MULTIPLE_CHOICE:
        case FieldTypes.DROP_DOWN:
            if (Array.isArray(value)) return { ...base, type: 'choices', choices: { values: value } };
            return { ...base, type: 'choice', choice: { value: String(value) } };
        default:
            return { ...base, type: 'text', text: String(value) };
    }
}

/** Display text of a submission's internal answer (same formatting as respondent answers). */
export function getInternalAnswerText(response: StandardFormResponseDto, field: StandardFormFieldDto): any {
    return getAnswerForField({ ...response, answers: response?.internalAnswers ?? {} }, field);
}

/** Header for an internal field's column in the responses table / CSV. */
export function getInternalColumnTitle(field: StandardFormFieldDto): string {
    return INTERNAL_COLUMN_PREFIX + (extractTextfromJSON(field)?.trim() || 'Untitled field');
}

/**
 * After a 409 (another team member saved in between): which of the fields I
 * changed did they change too? Those need my attention; the rest can be
 * re-sent against the new version without overwriting anyone.
 */
export function conflictingInternalFields(fields: StandardFormFieldDto[], changedIds: string[], baseline: Record<string, AnswerDto>, latest: Record<string, AnswerDto>): StandardFormFieldDto[] {
    return fields.filter((f) => changedIds.includes(f.id) && internalAnswerChanged(f, baseline[f.id], internalAnswerToInput(f, latest[f.id])));
}

/** Is the stored internal answer different from what the editor now holds? */
export function internalAnswerChanged(field: StandardFormFieldDto, stored: AnswerDto | undefined | null, value: InternalInputValue): boolean {
    return JSON.stringify(buildInternalAnswer(field, internalAnswerToInput(field, stored))) !== JSON.stringify(buildInternalAnswer(field, value));
}

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { isNumberedQuestion, questionNumbers } from '@app/utils/leaflet-sections';

/**
 * Question numbers outside the Leaflet style (which always numbers its
 * questions). Numbering is stored per page (`properties.showQuestionNumbers`
 * on a question page) and switched for the whole form from the builder's
 * Form tab.
 */

/** The form's question pages (welcome and ending pages live elsewhere). */
const questionPages = (slides: ReadonlyArray<StandardFormFieldDto> | undefined) => (slides ?? []).filter((slide) => !slide.type || slide.type === FieldTypes.SLIDE);

export type NumberingState = 'on' | 'off' | 'mixed';

/** Whether the form numbers its questions: on every page, on none, or on some. */
export function formNumberingState(slides: ReadonlyArray<StandardFormFieldDto> | undefined): NumberingState {
    const pages = questionPages(slides);
    const on = pages.filter((page) => !!page.properties?.showQuestionNumbers).length;
    if (on === 0) return 'off';
    return on === pages.length ? 'on' : 'mixed';
}

/**
 * The number of every question among `visibleFields` (what the respondent
 * sees on the page, in order), keyed by field id: "1.", "2.", … on a
 * one-page form, and "page.n" ("2.1") when the form has several pages, so a
 * number never repeats across the form.
 */
export function plainQuestionNumbers(visibleFields: ReadonlyArray<StandardFormFieldDto>, pageNumber: number, multiPage: boolean): Record<string, string> {
    if (multiPage) return questionNumbers(visibleFields, pageNumber);
    const numbers: Record<string, string> = {};
    let next = 1;
    for (const field of visibleFields) {
        if (!isNumberedQuestion(field)) continue;
        numbers[field.id] = `${next}.`;
        next += 1;
    }
    return numbers;
}

/** Whether the form has more than one question page. */
export const hasSeveralPages = (slides: ReadonlyArray<StandardFormFieldDto> | undefined) => questionPages(slides).length > 1;

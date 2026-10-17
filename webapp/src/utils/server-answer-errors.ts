import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { isRepeatingGroup, scopedFieldId } from '@app/utils/repeating-groups';

/**
 * The server re-checks a submission (backend services/answer_validation.py)
 * and refuses one with problems: 422 `{code: 'invalid_answers', errors:
 * [{fieldId, rule, item?}]}`. The respondent page normally catches all of
 * them first; when it did not (the form changed meanwhile, or the browser
 * and the server differ), these helpers put the server's problems on the
 * questions, the same way the page's own validation does.
 */

export interface ServerAnswerError {
    fieldId: string;
    rule: string;
    item?: number;
}

/** Server-only problems, with their own message (`respondent` RULE.*). */
export type ServerProblem = 'SERVER_TYPE' | 'SERVER_CHOICE';

const SERVER_PROBLEMS: ReadonlyArray<string> = ['SERVER_TYPE', 'SERVER_CHOICE'];

/** Server rule code -> the code the question wrapper understands. */
const CLIENT_CODES: Record<string, string> = {
    required: 'REQUIRED',
    too_short: 'TOO_SHORT',
    too_long: 'TOO_LONG',
    pattern: 'PATTERN',
    too_small: 'TOO_SMALL',
    too_large: 'TOO_LARGE',
    not_integer: 'NOT_INTEGER',
    too_few_choices: 'TOO_FEW_CHOICES',
    too_many_choices: 'TOO_MANY_CHOICES',
    type: 'SERVER_TYPE',
    choice: 'SERVER_CHOICE'
};

export const isServerProblem = (code: unknown): code is ServerProblem => typeof code === 'string' && SERVER_PROBLEMS.includes(code);

/** The answer problems in a failed submission (an RTK Query error), or null when it failed for another reason. */
export function serverAnswerErrors(error: any): ServerAnswerError[] | null {
    const data = error?.data;
    if (error?.status !== 422 || data?.code !== 'invalid_answers' || !Array.isArray(data.errors)) return null;
    const errors = data.errors.filter((e: any) => e && typeof e.fieldId === 'string' && typeof e.rule === 'string' && (e.item === undefined || (Number.isInteger(e.item) && e.item >= 0)));
    return errors.length ? errors : null;
}

/** Where each question id is shown: the page index and the id its wrapper is keyed by (a matrix row shows on its matrix). */
function questionPlaces(slides: StandardFormFieldDto[] | undefined): Map<string, { page: number; shownAs: string }> {
    const places = new Map<string, { page: number; shownAs: string }>();
    (slides ?? []).forEach((slide, page) => {
        (slide?.properties?.fields ?? []).forEach((field) => {
            places.set(field.id, { page, shownAs: field.id });
            const children = field.properties?.fields ?? [];
            if (field.type === FieldTypes.MATRIX) children.forEach((row) => places.set(row.id, { page, shownAs: field.id }));
            if (isRepeatingGroup(field)) children.forEach((child) => places.set(child.id, { page, shownAs: child.id }));
        });
    });
    return places;
}

/** The server's problems as page invalidations (same shape as the page's own), keyed by the id each question renders under. */
export function serverInvalidations(slides: StandardFormFieldDto[] | undefined, errors: ServerAnswerError[]): Record<string, string[]> {
    const places = questionPlaces(slides);
    const invalid: Record<string, string[]> = {};
    errors.forEach((error) => {
        const place = places.get(error.fieldId);
        const code = CLIENT_CODES[error.rule];
        if (!place || !code) return;
        const key = error.item !== undefined ? scopedFieldId(place.shownAs, error.item) : place.shownAs;
        if (!(invalid[key] ?? []).includes(code)) invalid[key] = [...(invalid[key] ?? []), code];
    });
    return invalid;
}

/** The first page with a problem the respondent can see, or -1. */
export function firstPageWithError(slides: StandardFormFieldDto[] | undefined, errors: ServerAnswerError[]): number {
    const places = questionPlaces(slides);
    const pages = errors.map((error) => (CLIENT_CODES[error.rule] ? places.get(error.fieldId)?.page : undefined)).filter((page): page is number => page !== undefined);
    return pages.length ? Math.min(...pages) : -1;
}

/**
 * Back history when returning to `target` to fix an answer: the pages
 * before it, as if the respondent had pressed Back, so the visited path
 * (which decides what is submitted) is retraced from there.
 */
export function historyBackTo(history: number[] | undefined, current: number, target: number): number[] {
    const trail = [...(history ?? [])];
    const at = trail.indexOf(target);
    if (at >= 0) return trail.slice(0, at);
    return target === current ? trail : [...trail, current];
}

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** What to tell the respondent about a server-only problem. */
export function serverProblemMessage(code: ServerProblem, t: Translate): string {
    return code === 'SERVER_CHOICE' ? t('RULE.SERVER_CHOICE') : t('RULE.SERVER_TYPE');
}

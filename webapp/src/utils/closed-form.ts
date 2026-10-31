import type { StandardFormDto } from '@app/models/dtos/form';

/**
 * A closed form reaches respondents without its questions and endings (the
 * server's closed stub: `unavailable: 'closed'`, the welcome page and its
 * look only).
 */
export const isClosedForm = (form?: Pick<StandardFormDto, 'unavailable'> | null) => form?.unavailable === 'closed';

/**
 * The page on screen for the respondent's place in the form: a closed form
 * shows its welcome page's closed notice on every page (their place is kept,
 * so a reopened form returns them to it), while an ending already reached
 * stays on screen. The form and the trust strip below it both follow this.
 */
export function shownSlide(form: Pick<StandardFormDto, 'unavailable'> | null | undefined, currentSlide: number): number {
    return isClosedForm(form) && currentSlide !== -2 ? -1 : currentSlide;
}

import type { StandardFormDto } from '@app/models/dtos/form';

/**
 * A form that takes no responses (closed, not open yet, or full) reaches
 * respondents without its questions and endings (the server's stub:
 * `unavailable` names why; the welcome page and its look only).
 */
export const isUnavailableForm = (form?: Pick<StandardFormDto, 'unavailable'> | null) => !!form?.unavailable;

/**
 * The page on screen for the respondent's place in the form: an unavailable
 * form shows its welcome page's notice on every page (their place is kept,
 * so a form that takes responses again returns them to it), while an ending
 * already reached stays on screen. The form and the trust strip below it both
 * follow this.
 */
export function shownSlide(form: Pick<StandardFormDto, 'unavailable'> | null | undefined, currentSlide: number): number {
    return isUnavailableForm(form) && currentSlide !== -2 ? -1 : currentSlide;
}

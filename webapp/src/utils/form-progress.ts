import { StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT } from '@app/models/types/form-builder-shared';
import { logicSourcesById, resolveJump } from '@app/utils/conditional-logic';

/** Whether the page at `slide` submits the form with the answers so far (a page jump to "submit"). */
export function pageEndsForm(fields: StandardFormFieldDto[] | undefined, slide: number, answers: Record<string, any>): boolean {
    const page = slide >= 0 ? fields?.[slide] : undefined;
    return !!page && resolveJump(page, answers, logicSourcesById(fields))?.target === JUMP_TARGET_SUBMIT;
}

/**
 * How much of the progress bar is filled, in percent: what "Page x of y" says
 * (page 1 of 3 is a third; the welcome and ending pages are not steps), full
 * on the ending and on a page that ends the form early (the header says "Last
 * page" there), and full for a one-page form. `currentSlide` is -1 on the
 * welcome page and -2 on the ending.
 */
export function progressPercent(fields: StandardFormFieldDto[] | undefined, currentSlide: number, answers: Record<string, any>): number {
    const pages = fields?.length || 1;
    if (currentSlide === -2 || pageEndsForm(fields, currentSlide, answers)) return 100;
    return (Math.min(Math.max(currentSlide, 0) + 1, pages) / pages) * 100;
}

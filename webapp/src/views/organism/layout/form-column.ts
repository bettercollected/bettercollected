import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';

/**
 * The respondent form's one column. The page header (Back, provenance,
 * progress), every question, the buttons, the welcome and ending pages, the
 * privacy panel and the trust strip all share these two values, so they line
 * up on one left and one right edge.
 *
 * - FORM_GUTTER: the side padding between the column and the screen edge
 *   (20px on phones, 32px from `sm` up).
 * - FORM_COLUMN: the column itself, 672px at most: a readable measure for
 *   labels and inputs, wide enough for two side-by-side half-width fields.
 */
export const FORM_GUTTER = 'px-5 sm:px-8';
export const FORM_COLUMN = 'w-full max-w-2xl';

/** Whether a page is set to "Left aligned" in the builder's page layout. */
export function isLeftAligned(layout?: FormSlideLayout | null) {
    return layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN;
}

/**
 * Where the column sits in the page: against the left gutter for "Left
 * aligned" pages, centred otherwise (including the image layouts, where it is
 * centred in its half of the page).
 */
export function columnPlacementClass(layout?: FormSlideLayout | null) {
    return isLeftAligned(layout) ? 'mr-auto' : 'mx-auto';
}

/**
 * How the welcome and ending pages align their text. "Centered" centres the
 * title, description, notes and button; "Left aligned" and the image layouts
 * keep a left edge.
 */
export function greetingTextAlignment(layout?: FormSlideLayout | null): 'center' | 'start' {
    return layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND ? 'center' : 'start';
}

/** Tailwind classes for `greetingTextAlignment` on a flex column. */
export function greetingAlignClass(layout?: FormSlideLayout | null) {
    return greetingTextAlignment(layout) === 'center' ? 'items-center text-center' : 'items-start text-left';
}

/**
 * The layout of the page a respondent is on: the welcome page (-1), the
 * ending page (-2) or a question page (its index).
 */
export function layoutOfPage(form: Partial<Pick<StandardFormDto, 'welcomePage' | 'thankyouPage' | 'fields'>> | undefined, currentSlide: number): FormSlideLayout | undefined {
    if (currentSlide === -1) return form?.welcomePage?.layout ?? undefined;
    if (currentSlide === -2) return form?.thankyouPage?.[0]?.layout ?? undefined;
    return form?.fields?.[currentSlide]?.properties?.layout ?? undefined;
}

/** A field's width on the 12-column grid (its "column width" setting), 1–12. */
export function clampSpan(field?: Pick<StandardFormFieldDto, 'properties'>) {
    return Math.min(12, Math.max(1, field?.properties?.colSpan ?? 12));
}

/**
 * Extra spacing for one field in a page's question stack. A text block
 * introduces what follows, so it sits closer to the next question (24px
 * instead of the 48px between questions) and keeps the full 48px above it:
 * more space above a heading than below. As the last field it keeps its
 * normal gap to the button.
 */
export function fieldSpacingClass(field: Pick<StandardFormFieldDto, 'type'>, isLast: boolean) {
    return field.type === FieldTypes.TEXT && !isLast ? '-mb-6' : '';
}

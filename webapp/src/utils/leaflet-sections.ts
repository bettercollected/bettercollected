import { JSONContent } from '@tiptap/react';

import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { isRepeatingGroup } from '@app/utils/repeating-groups';

/**
 * Leaflet numbering and sections (the Leaflet theme style).
 *
 * A page is a numbered section; its questions are numbered n.1, n.2, … in a
 * margin column. The rules:
 *
 * - The section number is the page's position in the form, the same number
 *   the header's "Page x of y" shows. A page-jump that skips a page skips its
 *   number too (1 → 3), exactly as the page counter does, so the two never
 *   disagree.
 * - Questions are numbered among the questions the respondent can see on that
 *   page right now: a question hidden by logic takes no number, so the visible
 *   sequence never has gaps (2.1, 2.2, 2.3). When logic reveals a question,
 *   it takes its place and the ones after it move up by one.
 * - Only questions are numbered. Text blocks, images and videos collect
 *   nothing and carry no number; a repeating group is one question (the
 *   questions inside each item are not numbered separately).
 */

// Answer fields that V2InputFields (used elsewhere) leaves out.
export const ALSO_ANSWERABLE: ReadonlyArray<FieldTypes> = [FieldTypes.LONG_TEXT, FieldTypes.LINK, FieldTypes.FILE_UPLOAD];

/** A field that collects an answer (and so carries a required/optional marker). */
export function isAnswerableField(field: Pick<StandardFormFieldDto, 'type'> | undefined | null): boolean {
    return !!field?.type && (V2InputFields.includes(field.type) || ALSO_ANSWERABLE.includes(field.type));
}

/** A field that takes an n.m number in the Leaflet style. */
export function isNumberedQuestion(field: StandardFormFieldDto | undefined | null): boolean {
    return isAnswerableField(field) || isRepeatingGroup(field);
}

/**
 * The n.m number of every question among `visibleFields` (the fields the
 * respondent sees on the page, in order), keyed by field id.
 */
export function questionNumbers(visibleFields: ReadonlyArray<StandardFormFieldDto>, sectionNumber: number): Record<string, string> {
    const numbers: Record<string, string> = {};
    let next = 1;
    for (const field of visibleFields) {
        if (!isNumberedQuestion(field)) continue;
        numbers[field.id] = `${sectionNumber}.${next}`;
        next += 1;
    }
    return numbers;
}

/** Plain text of a TipTap node (pipe chips read as their label). */
export function nodeText(node: JSONContent | undefined): string {
    if (!node) return '';
    if (node.type === 'text') return node.text ?? '';
    if (node.type === 'answerPipe') return node.attrs?.label || node.attrs?.pipeKey || '';
    return (node.content ?? []).map(nodeText).join('');
}

const hasText = (node: JSONContent) => nodeText(node).trim().length > 0;

/** Where a section's title comes from, in the order they are tried. */
export type SectionTitleSource = 'setting' | 'heading' | 'question' | 'empty';

export interface LeafletSection {
    /** The section bar's title, in full (also the accessible name). */
    title: string;
    /** The title as shown: long fallback titles are shortened with an ellipsis. */
    shortTitle: string;
    /** Whether the title is the creator's own (the page's section title or its opening heading). */
    titleFromPage: boolean;
    /** Where the title came from: the page's section title, its opening heading, its first question, or "Section n". */
    source: SectionTitleSource;
    /**
     * The text block shown in the intro band (with its opening heading moved
     * to the bar), or null when the page doesn't open with a text block or
     * nothing is left of it.
     */
    intro: StandardFormFieldDto | null;
    /** The id of the page's opening text block, which the band replaces in the list of fields. */
    openingTextId: string | null;
}

/** Longest section label shown before it is shortened. */
export const SECTION_LABEL_MAX = 60;

/** Shorten a label at a word boundary, with an ellipsis, when it runs past `max`. */
export function shortenLabel(text: string, max = SECTION_LABEL_MAX): string {
    const clean = text.replace(/\s+/g, ' ').trim();
    if (clean.length <= max) return clean;
    const cut = clean.slice(0, max - 1);
    const space = cut.lastIndexOf(' ');
    return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,;:.\-]+$/, '')}…`;
}

/** Plain text of a field's title (TipTap JSON or a plain string). */
export function fieldTitleText(field: StandardFormFieldDto | undefined): string {
    const title = field?.title;
    if (!title) return '';
    return (typeof title === 'string' ? title : nodeText(title as JSONContent)).replace(/\s+/g, ' ').trim();
}

/**
 * What a page shows in its section bar and intro band. The title is, in
 * order:
 *
 * 1. the page's own section title (`properties.sectionTitle`), when set;
 * 2. the opening heading: a page that opens with a text block gives the bar
 *    its first heading and the band the rest of the text;
 * 3. its first visible question, as the builder's page list names pages
 *    (shortened to 60 characters);
 * 4. `emptyLabel` ("Section 3") for a page with no questions at all.
 *
 * With a section title of its own, the opening text block stays whole in
 * the band, heading included. The form's title is never a section label.
 *
 * `visibleFields` should already have answer pipes resolved when the page is
 * shown to a respondent.
 */
export function leafletSection(visibleFields: ReadonlyArray<StandardFormFieldDto>, emptyLabel: string, sectionTitle?: string | null): LeafletSection {
    const fallback = (): Pick<LeafletSection, 'title' | 'shortTitle' | 'titleFromPage' | 'source'> => {
        const question = visibleFields.find((field) => isNumberedQuestion(field) && fieldTitleText(field));
        const title = question ? fieldTitleText(question) : emptyLabel;
        return { title, shortTitle: shortenLabel(title), titleFromPage: false, source: question ? 'question' : 'empty' };
    };
    const own = cleanSectionTitle(sectionTitle);
    const first = visibleFields[0];
    const opening = first?.type === FieldTypes.TEXT ? first : null;
    const doc = opening?.title;
    const blocks = doc && typeof doc !== 'string' ? ((doc as JSONContent).content ?? []) : [];
    const openingHasText = typeof doc === 'string' ? !!doc.trim() : blocks.some(hasText);

    if (own) {
        // The creator's own title, in full; the opening block stays whole.
        return { title: own, shortTitle: own, titleFromPage: true, source: 'setting', intro: opening && openingHasText ? opening : null, openingTextId: opening?.id ?? null };
    }
    if (!opening) return { ...fallback(), intro: null, openingTextId: null };
    if (!doc || typeof doc === 'string') return { ...fallback(), intro: openingHasText ? opening : null, openingTextId: opening.id };

    const headingIndex = blocks.findIndex((block) => hasText(block));
    const heading = headingIndex >= 0 && blocks[headingIndex].type === 'heading' ? blocks[headingIndex] : undefined;
    if (!heading) return { ...fallback(), intro: openingHasText ? opening : null, openingTextId: opening.id };

    const rest = blocks.slice(headingIndex + 1);
    const title = nodeText(heading).trim();
    return {
        title,
        // The creator's own heading is shown in full.
        shortTitle: title,
        titleFromPage: true,
        source: 'heading',
        intro: rest.some(hasText) ? { ...opening, title: { ...(doc as JSONContent), content: rest } } : null,
        openingTextId: opening.id
    };
}

/** Longest section title a creator can set (the backend's cap too). */
export const SECTION_TITLE_MAX = 120;

/** A page's section title as shown: whitespace collapsed and trimmed; '' when unset. */
export function cleanSectionTitle(value: string | null | undefined): string {
    return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
}

/** A page's section title (`properties.sectionTitle`). */
export function pageSectionTitle(page: StandardFormFieldDto | null | undefined): string {
    return cleanSectionTitle(page?.properties?.sectionTitle);
}

/**
 * Width of the margin column for a page's numbers: 34px, or 44px once a
 * number needs four characters ("2.10", "10.1"), so the number never runs
 * into the question it labels and every question on the page keeps one
 * left edge.
 */
export function leafletMarginWidth(numbers: Record<string, string>, sectionNumber: number): number {
    const longest = Math.max(String(sectionNumber).length, ...Object.values(numbers).map((n) => n.length));
    return longest >= 4 ? 44 : 34;
}

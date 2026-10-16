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

export interface LeafletSection {
    /** The section bar's title. */
    title: string;
    /** Whether the title came from the page's own opening heading. */
    titleFromPage: boolean;
    /**
     * The text block shown in the intro band (with its opening heading moved
     * to the bar), or null when the page doesn't open with a text block or
     * nothing is left of it.
     */
    intro: StandardFormFieldDto | null;
    /** The id of the page's opening text block, which the band replaces in the list of fields. */
    openingTextId: string | null;
}

/**
 * What a page shows in its section bar and intro band. A page that opens
 * with a text block gives the bar its first heading and the band the rest of
 * the text; a page without an opening heading uses `fallbackTitle` (the
 * form's title, like the running title of a leaflet).
 *
 * `visibleFields` should already have answer pipes resolved when the page is
 * shown to a respondent.
 */
export function leafletSection(visibleFields: ReadonlyArray<StandardFormFieldDto>, fallbackTitle: string): LeafletSection {
    const first = visibleFields[0];
    if (!first || first.type !== FieldTypes.TEXT) return { title: fallbackTitle, titleFromPage: false, intro: null, openingTextId: null };

    const doc = first.title;
    if (!doc || typeof doc === 'string') {
        return { title: fallbackTitle, titleFromPage: false, intro: doc && String(doc).trim() ? first : null, openingTextId: first.id };
    }
    const blocks = (doc as JSONContent).content ?? [];
    const headingIndex = blocks.findIndex((block) => hasText(block));
    const heading = headingIndex >= 0 && blocks[headingIndex].type === 'heading' ? blocks[headingIndex] : undefined;
    if (!heading) {
        return { title: fallbackTitle, titleFromPage: false, intro: blocks.some(hasText) ? first : null, openingTextId: first.id };
    }
    const rest = blocks.slice(headingIndex + 1);
    return {
        title: nodeText(heading).trim(),
        titleFromPage: true,
        intro: rest.some(hasText) ? { ...first, title: { ...(doc as JSONContent), content: rest } } : null,
        openingTextId: first.id
    };
}

import { generateHTML, JSONContent } from '@tiptap/react';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Extenstions, getPlaceholderValueForTitle } from '@app/views/molecules/rich-text-editor';

export function getHtmlFromJson(value: JSONContent | string | undefined) {
    if (!value) {
        return null;
    }
    if (typeof value === 'string') {
        return `<p><strong>${value}</strong></p>`;
    }
    return generateHTML(value, Extenstions);
}

/**
 * Plain-text rendering of a field title for creator-facing labels (table
 * headers, CSV columns, logic-source lists, "Used Fields"). Walks the TipTap
 * JSON directly instead of round-tripping through HTML, so answerPipe chips
 * render as their human label ("Page 1 · Enter Question") rather than leaking
 * editor syntax ("@Page 1 · Enter Question").
 */
export function extractTextfromJSON(field: StandardFormFieldDto): string {
    const title = field.title;
    if (!title) return getPlaceholderValueForTitle(field.type || FieldTypes.TEXT);
    if (typeof title === 'string') return title;

    const walk = (node: any): string => {
        if (!node) return '';
        if (node.type === 'text') return node.text ?? '';
        if (node.type === 'answerPipe') return node.attrs?.label || node.attrs?.pipeKey || '';
        const joined = (node.content ?? []).map(walk).join('');
        // Space between block nodes (paragraphs) so lines don't run together.
        return node.type === 'doc' ? joined : joined;
    };
    const text = (title.content ?? []).map(walk).join(' ').trim();
    return text || getPlaceholderValueForTitle(field.type || FieldTypes.TEXT);
}

import { JSONContent, generateHTML } from '@tiptap/react';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { sanitiseRichText } from '@app/utils/rich-text-style';
import { Extenstions, getPlaceholderValueForTitle } from '@app/views/molecules/rich-text-editor';

const HTML_ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

/** String titles are plain text (legacy titles, AI chat, PDF import): never markup. */
export function escapeHtml(text: string): string {
    return text.replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

export function getHtmlFromJson(value: JSONContent | string | undefined) {
    if (!value) {
        return null;
    }
    if (typeof value === 'string') {
        return `<p><strong>${escapeHtml(value)}</strong></p>`;
    }
    try {
        // font sizes and colours the editor never writes go into a style
        // attribute: dropped (stored titles may predate the check)
        return generateHTML(sanitiseRichText(value), Extenstions);
    } catch {
        // A title the editor's schema cannot render (an unknown node, mark or
        // attribute) must not break the page: show its text instead.
        return `<p>${escapeHtml(plainTextFromJson(value))}</p>`;
    }
}

/** The text of a TipTap document, answer pipes as their label. */
export function plainTextFromJson(node: any): string {
    if (!node || typeof node !== 'object') return '';
    if (node.type === 'text') return typeof node.text === 'string' ? node.text : '';
    if (node.type === 'answerPipe') return String(node.attrs?.label || node.attrs?.pipeKey || '');
    const parts = Array.isArray(node.content) ? node.content.map(plainTextFromJson) : [];
    return parts.join(node.type === 'doc' ? ' ' : '').trim();
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
    // Fields created before the rich-text title carry their question in the
    // legacy `value` string with a null title — prefer it over the generic
    // per-type placeholder.
    if (!title) return (typeof field.value === 'string' && field.value) || getPlaceholderValueForTitle(field.type || FieldTypes.TEXT);
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

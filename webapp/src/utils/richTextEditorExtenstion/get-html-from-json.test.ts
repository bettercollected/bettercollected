/**
 * Stored field titles are TipTap JSON written by the v2 editor: paragraphs
 * with textStyle marks (font size, colour), underline, and inline answerPipe
 * nodes. The v3 schema must keep rendering every one of them, or forms saved
 * before the upgrade would lose parts of their titles.
 */
import { describe, expect, it } from 'vitest';

import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

const storedTitle = {
    type: 'doc',
    content: [
        {
            type: 'paragraph',
            content: [
                { type: 'text', text: 'Hello ', marks: [{ type: 'bold' }, { type: 'underline' }] },
                {
                    type: 'text',
                    text: 'big red',
                    marks: [{ type: 'textStyle', attrs: { fontSize: '24px', color: '#ff0000' } }]
                },
                { type: 'text', text: ' ' },
                {
                    type: 'answerPipe',
                    attrs: { kind: 'field', pipeKey: 'q1', label: 'Page 1 · Your name', fallback: 'there' }
                }
            ]
        }
    ]
};

describe('getHtmlFromJson (TipTap 3 schema)', () => {
    it('renders titles saved by the v2 editor without dropping marks or pipes', () => {
        const html = getHtmlFromJson(storedTitle as any) ?? '';
        expect(html).toContain('<strong>');
        expect(html).toContain('<u>');
        expect(html).toContain('font-size: 24px');
        // TipTap 3 normalises colours to rgb(); same colour, different notation
        expect(html).toMatch(/color: (#ff0000|rgb\(255, 0, 0\))/);
        expect(html).toContain('data-pipe-key="q1"');
        expect(html).toContain('data-pipe-label="Page 1 · Your name"');
    });

    it('does not autolink URLs (link extension stays off, as in v2)', () => {
        const html =
            getHtmlFromJson({
                type: 'doc',
                content: [{ type: 'paragraph', content: [{ type: 'text', text: 'see https://example.com' }] }]
            } as any) ?? '';
        expect(html).not.toContain('<a ');
    });

    it('wraps legacy string titles in a bold paragraph', () => {
        expect(getHtmlFromJson('Plain title')).toBe('<p><strong>Plain title</strong></p>');
    });
});

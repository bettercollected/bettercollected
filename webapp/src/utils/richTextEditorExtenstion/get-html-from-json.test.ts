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

    it('treats string titles as text, never markup', () => {
        const html = getHtmlFromJson('Name <iframe srcdoc="<script>alert(1)</script>"></iframe> & <a href="x">co</a>') ?? '';
        expect(html).not.toContain('<iframe');
        expect(html).not.toContain('<a ');
        expect(html).toBe('<p><strong>Name &lt;iframe srcdoc=&quot;&lt;script&gt;alert(1)&lt;/script&gt;&quot;&gt;&lt;/iframe&gt; &amp; &lt;a href=&quot;x&quot;&gt;co&lt;/a&gt;</strong></p>');
    });
});

describe('text block headings', () => {
    it('renders heading levels from a stored title', () => {
        const html =
            getHtmlFromJson({
                type: 'doc',
                content: [
                    { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Section' }] },
                    { type: 'paragraph', content: [{ type: 'text', text: 'Details below.' }] }
                ]
            } as any) ?? '';
        expect(html).toContain('<h2>Section</h2>');
        expect(html).toContain('<p>Details below.</p>');
    });
});

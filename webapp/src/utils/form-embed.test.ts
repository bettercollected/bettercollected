import { describe, expect, it } from 'vitest';

import { CURRENT_EMBED_SCRIPT } from '@app/lib/embed/embed-script';

import { embedErrorKey, embedSnippet, escapeAttribute, iframeSnippet } from './form-embed';

describe('embed snippet', () => {
    it("is a placeholder with the form address and name, and the script of the form's own host", () => {
        expect(embedSnippet('https://forms.example.org/acme/forms/contact', 'Contact form')).toBe(
            `<div data-bc-form="https://forms.example.org/acme/forms/contact" data-bc-title="Contact form"></div>
<script async src="https://forms.example.org/embed/v1.js" integrity="${CURRENT_EMBED_SCRIPT.integrity}" crossorigin="anonymous"></script>`
        );
    });

    it('takes the script from a custom domain too', () => {
        expect(embedSnippet('https://forms.customer.nl/forms/aanvraag', 'Aanvraag')).toContain('src="https://forms.customer.nl/embed/v1.js"');
    });

    it('names an untitled form "Form" and tidies and caps the title', () => {
        expect(embedSnippet('https://forms.example.org/a/forms/b')).toContain('data-bc-title="Form"');
        expect(embedSnippet('https://forms.example.org/a/forms/b', '   ')).toContain('data-bc-title="Form"');
        expect(embedSnippet('https://forms.example.org/a/forms/b', 'Two\n  lines')).toContain('data-bc-title="Two lines"');
        const long = embedSnippet('https://forms.example.org/a/forms/b', 'x'.repeat(500));
        expect(long.match(/data-bc-title="(x+)"/)?.[1].length).toBe(120);
    });

    it('cannot be broken out of by a title or an address', () => {
        const hostile = '"><script>alert(1)</script><div a="';
        const snippet = embedSnippet('https://forms.example.org/a/forms/b', hostile);
        expect(snippet).not.toContain('<script>alert');
        expect(snippet.match(/<script/g)).toHaveLength(1);
        expect(snippet).toContain('data-bc-title="&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;&lt;div a=&quot;"');
        expect(embedSnippet('https://forms.example.org/a"b/forms/c', 'T')).toContain('data-bc-form="https://forms.example.org/a&quot;b/forms/c"');
        expect(escapeAttribute('a&b"<>')).toBe('a&amp;b&quot;&lt;&gt;');
    });
});

describe('iframe-only snippet', () => {
    it('is a plain frame of the form at a fixed height, with no script', () => {
        const snippet = iframeSnippet('https://forms.example.org/acme/forms/contact', 'Contact form');
        expect(snippet).toBe('<iframe src="https://forms.example.org/acme/forms/contact?embed=1" title="Contact form" width="100%" height="640" style="border:0" loading="lazy" referrerpolicy="origin" allow=""></iframe>');
        expect(snippet).not.toContain('<script');
    });

    it("keeps the address's own query, names an untitled form and cannot be broken out of", () => {
        expect(iframeSnippet('https://forms.example.org/a/forms/b?field_source=news', undefined, 800)).toContain('src="https://forms.example.org/a/forms/b?field_source=news&amp;embed=1" title="Form" width="100%" height="800"');
        const hostile = iframeSnippet('https://forms.example.org/a/forms/b', '"><script>alert(1)</script>');
        expect(hostile).not.toContain('<script>');
        expect(hostile.match(/<iframe/g)).toHaveLength(1);
    });
});

describe('embed errors', () => {
    it("map the server's code to a message key", () => {
        expect(embedErrorKey({ status: 422, data: { code: 'origin_wildcard' } })).toBe('STAFF.EMBED.ERROR.origin_wildcard');
        expect(embedErrorKey({ status: 422, data: { code: 'too_many_origins' } })).toBe('STAFF.EMBED.ERROR.too_many_origins');
        expect(embedErrorKey({ status: 403, data: 'x' })).toBe('STAFF.EMBED.ERROR.forbidden');
        expect(embedErrorKey({ status: 500 })).toBe('STAFF.EMBED.ERROR.generic');
        expect(embedErrorKey({ status: 422, data: { code: 'unknown_thing' } })).toBe('STAFF.EMBED.ERROR.generic');
        expect(embedErrorKey(undefined)).toBe('STAFF.EMBED.ERROR.generic');
    });
});

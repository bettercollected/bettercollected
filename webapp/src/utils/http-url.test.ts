import { describe, expect, it } from 'vitest';

import { httpUrl } from './http-url';

describe('httpUrl', () => {
    it.each(['https://example.org/privacy', 'http://example.org/', ' https://example.org/p?q=1 '])('keeps the http(s) link %s', (value) => {
        expect(httpUrl(value)).toBe(new URL(value.trim()).href);
    });

    it.each(['javascript:alert(1)', 'JavaScript:alert(1)', ' javascript:alert(1)', 'data:text/html,<b>x</b>', 'vbscript:x', 'ftp://example.org', '/privacy', 'example.org/privacy', '', '   ', null, undefined, 42])('drops %s', (value) => {
        expect(httpUrl(value)).toBeNull();
    });
});

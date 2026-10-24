import { afterEach, describe, expect, it, vi } from 'vitest';

import { browserMailLocale, pickMailLocale } from './mail-locale';

describe('mail locale', () => {
    afterEach(() => vi.restoreAllMocks());

    it('takes the first English or Dutch language, else English', () => {
        expect(pickMailLocale(['nl-BE', 'en'])).toBe('nl');
        expect(pickMailLocale(['de-DE', 'en-GB', 'nl'])).toBe('en');
        expect(pickMailLocale(['fr', 'NL'])).toBe('nl');
        expect(pickMailLocale(['de', undefined, null])).toBe('en');
        expect(pickMailLocale([])).toBe('en');
    });

    it("follows the browser's preferred languages", () => {
        vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['de-DE', 'nl-NL']);
        expect(browserMailLocale()).toBe('nl');
        vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue([]);
        vi.spyOn(window.navigator, 'language', 'get').mockReturnValue('nl');
        expect(browserMailLocale()).toBe('nl');
    });
});

import { describe, expect, it } from 'vitest';

import { pickRespondentLanguage } from './use-respondent-language';

describe('pickRespondentLanguage', () => {
    it('follows ?lang= on the share link first', () => {
        expect(pickRespondentLanguage('?lang=nl', ['en-US'])).toBe('nl');
        expect(pickRespondentLanguage('?lang=EN', ['nl-NL'])).toBe('en');
    });

    it("then the browser's first English or Dutch preference", () => {
        expect(pickRespondentLanguage('', ['de-DE', 'nl-BE', 'en'])).toBe('nl');
        expect(pickRespondentLanguage('?lang=fr', ['fr-FR', 'en-GB'])).toBe('en');
    });

    it('falls back to English', () => {
        expect(pickRespondentLanguage('', ['de-DE'])).toBe('en');
        expect(pickRespondentLanguage('', [])).toBe('en');
    });
});

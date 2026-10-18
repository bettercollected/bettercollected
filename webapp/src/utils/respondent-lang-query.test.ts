import { describe, expect, it } from 'vitest';

import { respondentLangQuery } from './respondent-lang-query';

describe('respondentLangQuery', () => {
    it('keeps a language the portal speaks', () => {
        expect(respondentLangQuery('nl')).toBe('?lang=nl');
        expect(respondentLangQuery('EN')).toBe('?lang=en');
        expect(respondentLangQuery(['nl', 'en'])).toBe('?lang=nl');
    });

    it('drops anything else', () => {
        expect(respondentLangQuery(undefined)).toBe('');
        expect(respondentLangQuery(null)).toBe('');
        expect(respondentLangQuery('')).toBe('');
        expect(respondentLangQuery('de')).toBe('');
        expect(respondentLangQuery('nl&next=https://example.com')).toBe('');
        expect(respondentLangQuery('/evil')).toBe('');
    });
});

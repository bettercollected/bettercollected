import { describe, expect, it } from 'vitest';

import { respondentLangQuery, respondentSignInUrl } from './respondent-lang-query';

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

describe('respondentSignInUrl', () => {
    it("carries the workspace, the way back and the respondent's language", () => {
        const url = new URL(respondentSignInUrl('ws-1', '/acme/forms/intake', 'nl'), 'https://forms.example');
        expect(url.pathname).toBe('/login');
        expect(Object.fromEntries(url.searchParams)).toEqual({ type: 'responder', workspace_id: 'ws-1', redirect_to: '/acme/forms/intake', lang: 'nl' });
    });

    it('leaves out a language the portal does not speak', () => {
        const url = new URL(respondentSignInUrl('ws-1', '/acme', 'de'), 'https://forms.example');
        expect(url.searchParams.has('lang')).toBe(false);
    });
});

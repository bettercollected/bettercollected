import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { COUNTRIES_MAX, COUNTRY_CODES, DEFAULT_COUNTRY, countryName, isCountryCode, questionCountries } from './countries';

const shared = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/countries-v1.json'), 'utf-8')) as { codes: string[]; maxCountries: number };

describe('the country list', () => {
    it('is the shared file', () => {
        expect([...COUNTRY_CODES]).toEqual(shared.codes);
        expect(COUNTRIES_MAX).toBe(shared.maxCountries);
        expect(COUNTRY_CODES).toHaveLength(249);
        expect(DEFAULT_COUNTRY).toBe('NL');
    });

    it('knows codes in capitals only', () => {
        for (const value of ['NL', 'BE', 'DE', 'US', 'AX']) expect(isCountryCode(value)).toBe(true);
        for (const value of ['nl', 'XX', 'NLD', 'N', '', undefined, 5, 'N1', ' NL', 'NL ']) expect(isCountryCode(value)).toBe(false);
    });

    it('names a country in the language asked, and falls back to the code', () => {
        expect(countryName('NL', 'nl')).toBe('Nederland');
        expect(countryName('BE', 'en')).toBe('Belgium');
        expect(countryName('ZZ', 'en')).toBe('Unknown Region');
        expect(countryName('NL', 'not a language !!')).toBe('NL');
    });

    it('allows the Netherlands only until a question lists countries', () => {
        expect(questionCountries(undefined)).toEqual(['NL']);
        expect(questionCountries({ properties: {} })).toEqual(['NL']);
        expect(questionCountries({ properties: { countries: [] } })).toEqual(['NL']);
        expect(questionCountries({ properties: { countries: ['BE', 'DE', 'XX'] } })).toEqual(['BE', 'DE']);
    });
});

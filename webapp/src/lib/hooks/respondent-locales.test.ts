import { describe, expect, it } from 'vitest';

import en from '../../../public/locales/en/respondent.json';
import nl from '../../../public/locales/nl/respondent.json';

/** Every leaf key as a dotted path, with its string value. */
function flatten(tree: Record<string, unknown>, prefix = ''): Record<string, string> {
    return Object.entries(tree).reduce<Record<string, string>>((acc, [key, value]) => {
        const path = prefix ? `${prefix}.${key}` : key;
        if (value && typeof value === 'object') Object.assign(acc, flatten(value as Record<string, unknown>, path));
        else acc[path] = String(value);
        return acc;
    }, {});
}

const placeholders = (text: string) => (text.match(/\{\{\s*\w+\s*\}\}|<\d+>/g) ?? []).map((p) => p.replace(/\s/g, '')).sort();

// Respondents read every form text in English or Dutch: a key missing in one
// language would silently fall back to English mid-form.
describe('respondent locales', () => {
    const enKeys = flatten(en);
    const nlKeys = flatten(nl);

    it('English and Dutch have the same keys', () => {
        expect(Object.keys(nlKeys).sort()).toEqual(Object.keys(enKeys).sort());
    });

    it('no empty strings', () => {
        Object.entries({ ...enKeys }).forEach(([key, value]) => expect(value.trim(), `en ${key}`).not.toBe(''));
        Object.entries({ ...nlKeys }).forEach(([key, value]) => expect(value.trim(), `nl ${key}`).not.toBe(''));
    });

    it('each translation keeps the same {{placeholders}} and <n> tags', () => {
        Object.keys(enKeys).forEach((key) => {
            expect(placeholders(nlKeys[key] ?? ''), key).toEqual(placeholders(enKeys[key]));
        });
    });
});

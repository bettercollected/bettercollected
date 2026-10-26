import { describe, expect, it } from 'vitest';

import rows from './dutch-first-templates.fixture.json';
import { checkPlainLanguage } from './index';

/**
 * The Dutch-first templates (backend/scripts/dutch_first_templates.py) are
 * written for the builder's own plain-language (B1) check: every sentence a
 * respondent reads must pass it with no hint at all, in Dutch and in
 * English. The fixture is a copy of the templates' prose, kept current by a
 * backend test (REGENERATE_TEMPLATE_PROSE=1 rewrites it).
 */
type Row = { template: string; language: 'nl' | 'en'; kind: string; text: string };

describe('Dutch-first templates and the plain-language check', () => {
    it('covers all five templates in both languages', () => {
        const seen = new Set((rows as Row[]).map((row) => `${row.template}:${row.language}`));
        expect(seen.size).toBe(10);
    });

    it.each(rows as Row[])('$template ($language) $kind: $text', ({ language, text }) => {
        expect(checkPlainLanguage(text, { formLanguage: language }).map((hint) => hint.rule)).toEqual([]);
    });
});

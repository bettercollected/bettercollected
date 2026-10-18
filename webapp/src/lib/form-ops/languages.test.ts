/**
 * set_form_language: the list the backend and the form spec share, undo
 * through the entity diff, and compaction. The op's results themselves are
 * in the shared corpus (corpus.test.ts).
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { applyOps } from './apply';
import { compactOps } from './compact';
import { FORM_LANGUAGES, checkedFormLanguage, formLanguageName } from './languages';
import { OpError } from './model';
import type { FormDoc, FormOp } from './types';

const SPEC_SCHEMA = resolve(__dirname, '../../../../docs/spec/form-spec-v1.schema.json');

const form = (settings?: Record<string, unknown>): FormDoc =>
    ({
        title: 'Taal',
        builderVersion: 'v2',
        ...(settings ? { settings } : {}),
        fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields: [{ id: 'q1', index: 0, type: 'short_text', title: 'Naam' }] } }]
    }) as FormDoc;

describe('form languages', () => {
    it('are the ones the form spec lists, in the same order', () => {
        const schema = JSON.parse(readFileSync(SPEC_SCHEMA, 'utf8'));
        const listed = schema.properties.language.anyOf.find((option: any) => option.enum).enum;
        expect(FORM_LANGUAGES.map((l) => l.code)).toEqual(listed);
    });

    it('each have their own name', () => {
        expect(formLanguageName('nl')).toBe('Nederlands');
        expect(formLanguageName('de')).toBe('Deutsch');
        expect(formLanguageName('en-GB')).toBeUndefined();
    });

    it('are checked as the backend checks them', () => {
        expect(checkedFormLanguage(' NL ')).toBe('nl');
        expect(checkedFormLanguage('')).toBeNull();
        expect(checkedFormLanguage(null)).toBeNull();
        expect(() => checkedFormLanguage('nl-NL')).toThrow(OpError);
    });
});

describe('set_form_language', () => {
    it('keeps the settings the form has and leaves the questions alone', () => {
        const before = form({ purpose: 'To plan.' });
        const { doc, results } = applyOps(before, [{ op: 'set_form_language', language: 'nl' }]);
        expect(results[0]).toMatchObject({ ok: true, message: "Set the form's language to Nederlands (nl)" });
        expect(doc.settings).toEqual({ purpose: 'To plan.', language: 'nl' });
        // unchanged pages keep their reference
        expect(doc.fields).toBe(before.fields);
    });

    it('is written whatever applySettings says: it is the form itself', () => {
        const { doc } = applyOps(form(), [{ op: 'set_form_language', language: 'fr' }], { applySettings: false });
        expect((doc.settings as any).language).toBe('fr');
    });

    it('is undone by its inverse, also back to no language', () => {
        for (const start of [undefined, { language: 'de' }]) {
            const before = form(start);
            const { doc, inverse } = applyOps(before, [{ op: 'set_form_language', language: 'nl' }]);
            expect(inverse).toEqual([{ op: 'set_form_language', language: start?.language ?? null }]);
            const undone = applyOps(doc, inverse).doc;
            expect((undone.settings as any)?.language ?? null).toBe(start?.language ?? null);
        }
    });

    it('clears with null and the inverse puts it back', () => {
        const before = form({ language: 'sv' });
        const { doc, inverse, results } = applyOps(before, [{ op: 'set_form_language', language: null }]);
        expect(results[0].message).toBe("Cleared the form's language");
        expect((doc.settings as any).language).toBeUndefined();
        expect(inverse).toEqual([{ op: 'set_form_language', language: 'sv' }]);
    });

    it('fails alone for a language off the list', () => {
        const ops: FormOp[] = [
            { op: 'set_form_language', language: 'tlh' },
            { op: 'set_form_language', language: 'fi' }
        ];
        const { doc, results } = applyOps(form(), ops);
        expect(results.map((r) => r.ok)).toEqual([false, true]);
        expect(results[0].message).toContain('is not a language a form can be set to');
        expect((doc.settings as any).language).toBe('fi');
    });

    it('compacts to the last one', () => {
        const ops: FormOp[] = [
            { op: 'set_form_language', language: 'nl' },
            { op: 'set_form_language', language: 'en' }
        ];
        expect(compactOps(ops)).toEqual([ops[1]]);
    });
});

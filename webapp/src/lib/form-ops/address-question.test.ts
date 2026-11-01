import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { applyOps } from './apply';
import { ADDRESS_GATE, ADDRESS_QUESTION_DISABLED_MESSAGE, ADDRESS_TYPES, GATED_TYPES, gatedSignatures, gatesOff, newOrChangedQuestions, pageHoldsGatedQuestion, signature, typeIsOff } from './new-question-types';
import type { FormDoc, FormField, FormOp } from './types';

const python = readFileSync(resolve(__dirname, '../../../../backend/backend/app/services/new_question_types.py'), 'utf-8');
const doc = (fields: any[]): FormDoc => ({ title: 'T', builderVersion: 'v2', fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields } } as FormField] }) as FormDoc;
const ADDRESS = { id: 'a', index: 0, type: 'address', title: 'Home', properties: { countries: ['NL', 'BE'], addressLookup: false } };
const TEXT = { id: 's', index: 1, type: 'short_text', title: 'Name' };
const base = () => doc([ADDRESS, TEXT]);
const run = (ops: FormOp[], enabled: boolean) => applyOps(base(), ops, { atomic: false, skipInverse: true, addressQuestion: enabled });

describe('the switch for the address question', () => {
    it('is the backend list, apart from the other types', () => {
        expect([...ADDRESS_TYPES]).toEqual(['address']);
        expect(GATED_TYPES.has('address')).toBe(false);
        const types = /ADDRESS_TYPES = frozenset\(\{([^}]*)\}\)/.exec(python)![1].match(/"([a-z_]+)"/g)!.map((type) => type.slice(1, -1));
        expect([...ADDRESS_TYPES]).toEqual(types);
    });

    it('says what the backend says, byte for byte', () => {
        const block = /\nADDRESS_DISABLED_MESSAGE = \(\n([\s\S]*?)\n\)\n/.exec(python)![1];
        const text = [...block.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((match) => match[1]).join('');
        expect(ADDRESS_QUESTION_DISABLED_MESSAGE).toBe(text);
        expect(ADDRESS_GATE.message).toBe(text);
    });

    it('reads the countries and the lookup into the signature, as the backend does', () => {
        expect(signature({ ...ADDRESS, title: 'Where' } as FormField)).toBe(signature(ADDRESS as FormField));
        expect(signature({ ...ADDRESS, properties: { countries: ['NL'], addressLookup: false } } as FormField)).not.toBe(signature(ADDRESS as FormField));
        expect(signature({ ...ADDRESS, properties: { countries: ['NL', 'BE'], addressLookup: true } } as FormField)).not.toBe(signature(ADDRESS as FormField));
        expect([...gatedSignatures(base()).keys()]).toEqual(['a']);
        expect(python).toContain('"countries": _get(props, "countries")');
        expect(python).toContain('"addressLookup": _get(props, "address_lookup")');
    });

    it('is a gate of its own: the other switch does not open it', () => {
        expect(gatesOff({ newQuestionTypes: true, addressQuestion: false })).toEqual([ADDRESS_GATE]);
        expect(gatesOff({ newQuestionTypes: false, addressQuestion: true })).not.toContain(ADDRESS_GATE);
        expect(gatesOff({})).toEqual([]);
        expect(typeIsOff('address', { newQuestionTypes: true, addressQuestion: false })).toBe(true);
        expect(typeIsOff('address', { newQuestionTypes: false, addressQuestion: true })).toBe(false);
        expect(typeIsOff('time', { newQuestionTypes: true, addressQuestion: false })).toBe(false);
    });

    it('finds the questions that are new or changed, and lets a stored one stay', () => {
        const stored = gatedSignatures(base());
        expect(newOrChangedQuestions(base(), stored, ADDRESS_GATE)).toEqual([]);
        expect(newOrChangedQuestions(doc([{ ...ADDRESS, title: 'Renamed', index: 3 }, TEXT]), stored, ADDRESS_GATE)).toEqual([]);
        expect(newOrChangedQuestions(doc([{ ...ADDRESS, properties: { countries: ['NL'] } }, TEXT]), stored, ADDRESS_GATE)).toEqual(['a']);
        expect(newOrChangedQuestions(doc([ADDRESS, { ...ADDRESS, id: 'b' }, TEXT]), stored, ADDRESS_GATE)).toEqual(['b']);
    });

    it('tells a page that holds one', () => {
        const page = base().fields![0] as FormField;
        expect(pageHoldsGatedQuestion(page, { newQuestionTypes: true, addressQuestion: false })).toBe(true);
        expect(pageHoldsGatedQuestion(page, { newQuestionTypes: true, addressQuestion: true })).toBe(false);
    });

    it('refuses an op that adds or changes an address question while off, and lets the rest through', () => {
        const add = run([{ op: 'add_field', pageId: 'p1', field: { title: 'Work', type: 'address' } }], false);
        expect(add.results[0].ok).toBe(false);
        expect(add.results[0].message).toBe(ADDRESS_QUESTION_DISABLED_MESSAGE);
        expect(run([{ op: 'add_field', pageId: 'p1', field: { title: 'Work', type: 'address' } }], true).results[0].ok).toBe(true);
        const change = run([{ op: 'update_field', fieldId: 'a', patch: { countries: ['NL'] } }], false);
        expect(change.results[0].message).toBe(ADDRESS_QUESTION_DISABLED_MESSAGE);
        expect(run([{ op: 'update_field', fieldId: 'a', patch: { title: 'Where do you live?' } }], false).results[0].ok).toBe(true);
        // the other types are not affected by this switch
        expect(run([{ op: 'add_field', pageId: 'p1', field: { title: 'At', type: 'time' } }], false).results[0].ok).toBe(true);
    });
});

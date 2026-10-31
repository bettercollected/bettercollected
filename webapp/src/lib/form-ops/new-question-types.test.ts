import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { applyOps } from './apply';
import { GATED_TYPES, NEW_QUESTION_TYPES_DISABLED_MESSAGE, gatedSignatures, isGatedQuestion, newOrChangedQuestions, pageHoldsGatedQuestion, signature } from './new-question-types';
import type { FormDoc, FormField, FormOp } from './types';

const doc = (fields: any[]): FormDoc => ({ title: 'T', builderVersion: 'v2', fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields } } as FormField] }) as FormDoc;
const TIME = { id: 't', index: 0, type: 'time', title: 'At', properties: { minTime: '08:00' } };
const MONEY = { id: 'm', index: 1, type: 'currency', title: 'Pay', properties: { currencies: ['EUR'] }, validations: { minValue: 1 } };
const DAY = { id: 'd', index: 2, type: 'day', title: 'Born' };
const TEXT = { id: 's', index: 3, type: 'short_text', title: 'Name' };
const RANGE = { id: 'r', index: 4, type: 'date_range', title: 'Stay', properties: { dateRules: [{ comparison: 'on_or_after', target: 'date', date: '2026-01-01' }] } };
const TAGS = { id: 'g', index: 5, type: 'tags', title: 'Topics', validations: { maxChoices: 5, maxLength: 20 } };
const base = () => doc([TIME, MONEY, DAY, TEXT]);
const ranged = () => doc([TEXT, RANGE, TAGS]);

const run = (ops: FormOp[], enabled: boolean, atomic = false) => applyOps(base(), ops, { atomic, skipInverse: true, newQuestionTypes: enabled });

describe('the switch for the newer question types', () => {
    it('is the backend list: time, day, currency, date range and tags', () => {
        expect([...GATED_TYPES].sort()).toEqual(['currency', 'date_range', 'day', 'tags', 'time']);
        const python = readFileSync(resolve(__dirname, '../../../../backend/backend/app/services/new_question_types.py'), 'utf-8');
        const types = /GATED_TYPES = frozenset\(\{([^}]*)\}\)/
            .exec(python)![1]
            .match(/"([a-z_]+)"/g)!
            .map((type) => type.slice(1, -1));
        expect([...GATED_TYPES].sort()).toEqual(types.sort());
    });

    it('says what the backend says, byte for byte', () => {
        const python = readFileSync(resolve(__dirname, '../../../../backend/backend/app/services/new_question_types.py'), 'utf-8');
        const block = /DISABLED_MESSAGE = \(\n([\s\S]*?)\n\)\n/.exec(python)![1];
        const text = [...block.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((match) => match[1]).join('');
        expect(NEW_QUESTION_TYPES_DISABLED_MESSAGE).toBe(text);
    });

    it('reads a signature from the type and its own settings only', () => {
        expect(signature({ ...TIME, title: 'Arrival', properties: { minTime: '08:00', label: 'x' } } as FormField)).toBe(signature(TIME as FormField));
        expect(signature({ ...TIME, properties: { minTime: '09:00' } } as FormField)).not.toBe(signature(TIME as FormField));
        expect(signature({ ...MONEY, validations: { minValue: 1, maxValue: 5 } } as FormField)).not.toBe(signature(MONEY as FormField));
        expect([...gatedSignatures(base()).keys()].sort()).toEqual(['d', 'm', 't']);
    });

    it('reads the number and the length of tags into a tags question’s signature, as the backend does', () => {
        expect(signature({ ...TAGS, title: 'Interests' } as FormField)).toBe(signature(TAGS as FormField));
        for (const validations of [
            { maxChoices: 4, maxLength: 20 },
            { maxChoices: 5, maxLength: 21 },
            { minChoices: 1, maxChoices: 5, maxLength: 20 }
        ]) {
            expect(signature({ ...TAGS, validations } as FormField)).not.toBe(signature(TAGS as FormField));
        }
        // the dates a range may have are part of it, its title is not
        expect(signature({ ...RANGE, properties: { dateRules: [{ comparison: 'before', target: 'today' }] } } as FormField)).not.toBe(signature(RANGE as FormField));
        expect(signature({ ...RANGE, title: 'Holiday' } as FormField)).toBe(signature(RANGE as FormField));
        expect([...gatedSignatures(ranged()).keys()].sort()).toEqual(['g', 'r']);
    });

    it('counts new questions, changed settings and changed types, not removals', () => {
        const stored = gatedSignatures(base());
        expect(newOrChangedQuestions(base(), stored)).toEqual([]);
        expect(newOrChangedQuestions(doc([{ ...TEXT, type: 'time' }]), stored)).toEqual(['s']);
        expect(newOrChangedQuestions(doc([TEXT]), stored)).toEqual([]);
        expect(newOrChangedQuestions(doc([{ ...MONEY, properties: { currencies: ['EUR', 'USD'] } }]), stored)).toEqual(['m']);
    });

    it('refuses an op that adds one, with the message the backend gives', () => {
        const { results, doc: after } = run([{ op: 'add_field', pageId: 'p1', field: { title: 'Out', type: 'time' } } as FormOp], false, true);
        expect(results[0].ok).toBe(false);
        expect(results[0].message).toBe(NEW_QUESTION_TYPES_DISABLED_MESSAGE);
        expect(after).toEqual(base());
    });

    it('lets the same op through while it is on, and by default', () => {
        const op = { op: 'add_field', pageId: 'p1', field: { title: 'Out', type: 'time' } } as FormOp;
        expect(run([op], true).results[0].ok).toBe(true);
        expect(applyOps(base(), [op], { skipInverse: true }).results[0].ok).toBe(true);
    });

    it('keeps applying what is allowed in a partial batch, and undoes only the refused op', () => {
        const { results, doc: after } = run(
            [
                { op: 'update_field', fieldId: 's', patch: { title: 'Remark' } },
                { op: 'update_field', fieldId: 't', patch: { minTime: '09:00' } },
                { op: 'update_field', fieldId: 't', patch: { title: 'Arrival' } }
            ] as FormOp[],
            false
        );
        expect(results.map((r) => r.ok)).toEqual([true, false, true]);
        const fields = (after.fields![0].properties!.fields as FormField[]).map((f) => [f.id, f.title, f.properties?.minTime]);
        expect(fields).toContainEqual(['t', 'Arrival', '08:00']);
        expect(fields).toContainEqual(['s', 'Remark', undefined]);
    });

    it('lets questions of these types be moved, removed and changed to an older type', () => {
        const { results } = run(
            [
                { op: 'move_field', fieldId: 'm', index: 0 },
                { op: 'remove_field', fieldId: 't' },
                { op: 'replace_field', field: { id: 'd', index: 1, type: 'short_text', title: 'Born' } }
            ] as FormOp[],
            false
        );
        expect(results.filter((r) => !r.ok).map((r) => r.message)).toEqual([]);
    });

    it('counts a second question with a stored id as new', () => {
        const stored = gatedSignatures(doc([TIME]));
        const twice = doc([TIME, { ...TIME, title: 'Again' }]);
        expect(newOrChangedQuestions(twice, stored)).toEqual(['t']);
        expect(newOrChangedQuestions(twice, gatedSignatures(twice))).toEqual([]);
        // a check does not use up the stored copies
        expect(newOrChangedQuestions(twice, stored)).toEqual(['t']);
        expect(newOrChangedQuestions(doc([TIME]), stored)).toEqual([]);
    });

    it('is not thrown by a payload that has a list or an object for a type', () => {
        for (const odd of [['x'], { a: 1 }, 3, null]) {
            const { results } = run([{ op: 'add_field', pageId: 'p1', field: { title: 'c', type: 'calculated', expression: { type: odd } } } as unknown as FormOp], false);
            expect(results[0].ok).toBe(false);
            expect(results[0].message).not.toBe(NEW_QUESTION_TYPES_DISABLED_MESSAGE);
        }
        const patched = run([{ op: 'update_field', fieldId: 's', patch: { expression: { type: ['x'] } } } as unknown as FormOp], false);
        expect(patched.results[0].ok).toBe(false);
    });

    it('refuses the date range and tags questions the way it refuses the others, and lets them be moved, titled and removed', () => {
        const add = (type: string) => applyOps(ranged(), [{ op: 'add_field', pageId: 'p1', field: { title: 'New', type } } as FormOp], { atomic: true, skipInverse: true, newQuestionTypes: false });
        for (const type of ['date_range', 'tags']) {
            const { results, doc: after } = add(type);
            expect(results[0].message).toBe(NEW_QUESTION_TYPES_DISABLED_MESSAGE);
            expect(after).toEqual(ranged());
        }
        const refused = applyOps(
            ranged(),
            [
                { op: 'set_field_validation', fieldId: 'g', validation: { maxChoices: 3 } },
                { op: 'set_field_validation', fieldId: 'g', validation: { maxLength: 10 } },
                { op: 'update_field', fieldId: 'r', patch: { dateRules: [{ comparison: 'before', target: 'today' }] } }
            ] as FormOp[],
            { skipInverse: true, newQuestionTypes: false }
        );
        expect(refused.results.map((r) => r.message)).toEqual([NEW_QUESTION_TYPES_DISABLED_MESSAGE, NEW_QUESTION_TYPES_DISABLED_MESSAGE, NEW_QUESTION_TYPES_DISABLED_MESSAGE]);
        const allowed = applyOps(
            ranged(),
            [
                { op: 'update_field', fieldId: 'g', patch: { title: 'Interests' } },
                { op: 'set_field_validation', fieldId: 'r', validation: { required: true } },
                { op: 'move_field', fieldId: 'g', index: 0 },
                { op: 'remove_field', fieldId: 'r' }
            ] as FormOp[],
            { skipInverse: true, newQuestionTypes: false }
        );
        expect(allowed.results.filter((r) => !r.ok).map((r) => r.message)).toEqual([]);
        // the same ops go through while the switch is on
        expect(applyOps(ranged(), [{ op: 'set_field_validation', fieldId: 'g', validation: { maxChoices: 3 } }] as FormOp[], { skipInverse: true, newQuestionTypes: true }).results[0].ok).toBe(true);
    });

    it('knows a question and a page that hold a type behind the switch', () => {
        expect(isGatedQuestion(RANGE as FormField) && isGatedQuestion(TAGS as FormField)).toBe(true);
        expect(pageHoldsGatedQuestion(ranged().fields![0])).toBe(true);
        expect(isGatedQuestion(TIME as FormField)).toBe(true);
        expect(isGatedQuestion(TEXT as FormField)).toBe(false);
        expect(isGatedQuestion(undefined)).toBe(false);
        expect(pageHoldsGatedQuestion(base().fields![0])).toBe(true);
        expect(pageHoldsGatedQuestion(doc([TEXT]).fields![0])).toBe(false);
        expect(pageHoldsGatedQuestion(undefined)).toBe(false);
    });

    it('asks nothing new when a date rule is taken away, and something when one is added', () => {
        const ruleA = { comparison: 'after', target: 'field', fieldId: 's' };
        const ruleB = { comparison: 'before', target: 'today' };
        const day = (rules: unknown[]) => ({ id: 'd', index: 0, type: 'day', title: 'Moved in', properties: { dateRules: rules } });
        const stored = gatedSignatures(doc([day([ruleA, ruleB])]));
        expect(newOrChangedQuestions(doc([day([ruleB])]), stored)).toEqual([]);
        expect(newOrChangedQuestions(doc([day([])]), stored)).toEqual([]);
        expect(newOrChangedQuestions(doc([day([ruleA, ruleB])]), stored)).toEqual([]);
        expect(newOrChangedQuestions(doc([day([ruleA, ruleB, { comparison: 'on_or_after', target: 'date', date: '1900-01-01' }])]), stored)).toEqual(['d']);
        expect(newOrChangedQuestions(doc([day([{ comparison: 'on_or_after', target: 'date', date: '1900-01-01' }])]), stored)).toEqual(['d']);
    });

    it('lets the date question a day question\'s rule points at be removed while the switch is off', () => {
        const start = { id: 's', index: 0, type: 'date', title: 'Start' };
        const day = { id: 'd', index: 1, type: 'day', title: 'Moved in', properties: { dateRules: [{ comparison: 'after', target: 'field', fieldId: 's' }] } };
        const { results, doc: after } = applyOps(doc([start, day]), [{ op: 'remove_field', fieldId: 's' } as FormOp], { atomic: true, skipInverse: true, newQuestionTypes: false });
        expect(results[0].ok).toBe(true);
        const left = (after.fields![0].properties!.fields as FormField[]).map((f) => [f.id, f.properties?.dateRules]);
        expect(left).toEqual([['d', undefined]]);
    });
});

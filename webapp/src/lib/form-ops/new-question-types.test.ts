import { describe, expect, it } from 'vitest';

import { applyOps } from './apply';
import { GATED_TYPES, NEW_QUESTION_TYPES_DISABLED_MESSAGE, gatedSignatures, isGatedQuestion, newOrChangedQuestions, pageHoldsGatedQuestion, signature } from './new-question-types';
import type { FormDoc, FormField, FormOp } from './types';

const doc = (fields: any[]): FormDoc => ({ title: 'T', builderVersion: 'v2', fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields } } as FormField] }) as FormDoc;
const TIME = { id: 't', index: 0, type: 'time', title: 'At', properties: { minTime: '08:00' } };
const MONEY = { id: 'm', index: 1, type: 'currency', title: 'Pay', properties: { currencies: ['EUR'] }, validations: { minValue: 1 } };
const DAY = { id: 'd', index: 2, type: 'day', title: 'Born' };
const TEXT = { id: 's', index: 3, type: 'short_text', title: 'Name' };
const base = () => doc([TIME, MONEY, DAY, TEXT]);

const run = (ops: FormOp[], enabled: boolean, atomic = false) => applyOps(base(), ops, { atomic, skipInverse: true, newQuestionTypes: enabled });

describe('the switch for the newer question types', () => {
    it('is the backend list: time, day and currency', () => {
        expect([...GATED_TYPES].sort()).toEqual(['currency', 'day', 'time']);
    });

    it('reads a signature from the type and its own settings only', () => {
        expect(signature({ ...TIME, title: 'Arrival', properties: { minTime: '08:00', label: 'x' } } as FormField)).toBe(signature(TIME as FormField));
        expect(signature({ ...TIME, properties: { minTime: '09:00' } } as FormField)).not.toBe(signature(TIME as FormField));
        expect(signature({ ...MONEY, validations: { minValue: 1, maxValue: 5 } } as FormField)).not.toBe(signature(MONEY as FormField));
        expect([...gatedSignatures(base()).keys()].sort()).toEqual(['d', 'm', 't']);
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

    it('knows a question and a page that hold a type behind the switch', () => {
        expect(isGatedQuestion(TIME as FormField)).toBe(true);
        expect(isGatedQuestion(TEXT as FormField)).toBe(false);
        expect(isGatedQuestion(undefined)).toBe(false);
        expect(pageHoldsGatedQuestion(base().fields![0])).toBe(true);
        expect(pageHoldsGatedQuestion(doc([TEXT]).fields![0])).toBe(false);
        expect(pageHoldsGatedQuestion(undefined)).toBe(false);
    });
});

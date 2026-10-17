import { describe, expect, it } from 'vitest';

import { form200, idMaker, largeForm, randomOp, rng, smallForm } from './__fixtures__/forms';
import { applyOps } from './apply';
import { compactOps } from './compact';
import { entityDiff } from './entity-diff';
import type { FormDoc, FormOp } from './types';

/** Random batches, each op drawn against the document as the batch so far left it. */
function randomBatch(doc: FormDoc, seed: number, length: number, prefix: string): FormOp[] {
    const random = rng(seed);
    const newId = idMaker(`${prefix}x`);
    const ops: FormOp[] = [];
    let current = doc;
    for (let i = 0; i < length; i++) {
        const op = randomOp(current, random, newId);
        ops.push(op);
        current = applyOps(current, [op], { newId: idMaker(`${prefix}${i}-`), skipInverse: true }).doc;
    }
    return ops;
}

const fixtures: Array<[string, () => FormDoc]> = [
    ['small form', smallForm],
    ['generated 200-question form', () => largeForm()],
    ['shared 200-question fixture', form200]
];

describe.each(fixtures)('inverse ops on the %s', (_name, make) => {
    it('apply(inverse) gives back the original, whatever the batch', () => {
        let tried = 0;
        let ok = 0;
        for (let seed = 1; seed <= 60; seed++) {
            const original = make();
            const ops = randomBatch(original, seed, 1 + (seed % 12), `s${seed}-`);
            const { doc, inverse, results } = applyOps(original, ops, { newId: idMaker(`s${seed}-`) });
            tried += results.length;
            ok += results.filter((r) => r.ok).length;
            const undone = applyOps(doc, inverse, { atomic: true });
            expect(undone.results.filter((r) => !r.ok)).toEqual([]);
            expect(undone.doc, `seed ${seed}: ${JSON.stringify(ops)}`).toEqual(original);
            // and redo: the inverse of the undo brings the batch back
            const redone = applyOps(undone.doc, undone.inverse, { atomic: true });
            expect(redone.doc).toEqual(doc);
        }
        // the batches must mostly apply, or the test proves little
        expect(ok / tried).toBeGreaterThan(0.6);
    });
});

describe('entityDiff', () => {
    it('apply(entityDiff(a, b), a) == b for documents a batch apart', () => {
        for (let seed = 100; seed < 160; seed++) {
            const a = smallForm();
            const b = applyOps(a, randomBatch(a, seed, 8, `d${seed}-`), { newId: idMaker(`d${seed}-`), skipInverse: true }).doc;
            const out = applyOps(a, entityDiff(a, b), { atomic: true });
            expect(out.results.filter((r) => !r.ok)).toEqual([]);
            expect(out.doc, `seed ${seed}`).toEqual(b);
        }
    });

    it('apply(entityDiff(b, c), b) == c for two unrelated edits of one form', () => {
        for (let seed = 200; seed < 240; seed++) {
            const a = largeForm(4, 8);
            const b = applyOps(a, randomBatch(a, seed, 10, `b${seed}-`), { newId: idMaker(`b${seed}-`), skipInverse: true }).doc;
            const c = applyOps(a, randomBatch(a, seed + 1000, 10, `c${seed}-`), { newId: idMaker(`c${seed}-`), skipInverse: true }).doc;
            const out = applyOps(b, entityDiff(b, c), { atomic: true });
            expect(out.results.filter((r) => !r.ok)).toEqual([]);
            expect(out.doc, `seed ${seed}`).toEqual(c);
        }
    });

    it('is empty between equal documents and minimal for one change', () => {
        const a = smallForm();
        expect(entityDiff(a, a)).toEqual([]);
        expect(entityDiff(a, smallForm())).toEqual([]);
        const b = applyOps(a, [{ op: 'update_field', fieldId: 'bio', patch: { title: 'x' } }]).doc;
        expect(entityDiff(a, b)).toEqual([{ op: 'replace_field', field: b.fields[1].properties!.fields![1] }]);
    });

    it('puts back what a removal dropped on other questions', () => {
        const a = smallForm();
        const { doc, inverse, touched } = applyOps(a, [{ op: 'remove_field', fieldId: 'start' }]);
        expect([...touched.fields]).toEqual(expect.arrayContaining(['end', 'start']));
        expect(inverse.map((op) => op.op)).toEqual(['insert_field', 'replace_field']);
        expect(applyOps(doc, inverse).doc).toEqual(a);
    });
});

describe('compactOps', () => {
    const title = (fieldId: string, text: string): FormOp => ({ op: 'update_field', fieldId, patch: { title: text } });

    it('folds consecutive edits of the same key of the same question', () => {
        expect(compactOps([title('a', 'H'), title('a', 'He'), title('a', 'Hel')])).toEqual([title('a', 'Hel')]);
        expect(compactOps([title('a', 'H'), title('b', 'x'), title('a', 'He')])).toEqual([title('a', 'H'), title('b', 'x'), title('a', 'He')]);
        const both: FormOp = { op: 'update_field', fieldId: 'a', patch: { title: 'x', required: true } };
        expect(compactOps([title('a', 'H'), both])).toEqual([both]);
        expect(compactOps([both, title('a', 'H')])).toEqual([both, title('a', 'H')]);
    });

    it('keeps the last whole-value op', () => {
        const replace = (t: string): FormOp => ({ op: 'replace_field', fieldId: 'a', field: { id: 'a', index: 0, type: 'short_text', title: t } });
        expect(compactOps([replace('1'), replace('2')])).toEqual([replace('2')]);
        expect(
            compactOps([
                { op: 'set_hidden_fields', names: ['a'] },
                { op: 'set_hidden_fields', names: [] }
            ])
        ).toEqual([{ op: 'set_hidden_fields', names: [] }]);
    });

    it('has the effect of the ops it folds', () => {
        const a = smallForm();
        const ops = ['Y', 'Yo', 'You', 'Your'].map((t) => title('name', t));
        expect(applyOps(a, compactOps(ops)).doc).toEqual(applyOps(a, ops).doc);
        // coalesced undo: the inverses of several steps, folded, still undo them all
        let doc = a;
        const inverses: FormOp[] = [];
        for (const op of ops) {
            const out = applyOps(doc, [op]);
            doc = out.doc;
            inverses.unshift(...out.inverse);
        }
        const folded = compactOps(inverses);
        expect(folded).toHaveLength(1);
        expect(applyOps(doc, folded).doc).toEqual(a);
    });
});

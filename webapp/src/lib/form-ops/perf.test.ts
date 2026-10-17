import { describe, expect, it } from 'vitest';

import { form200, idMaker, pageIds, questionIds } from './__fixtures__/forms';
import { applyOps } from './apply';
import type { FormOp } from './types';

/**
 * The time `fn` takes, after a warm-up: the lower quartile of `runs`
 * timings. The test files run in parallel, so single runs are slowed by
 * whatever else the machine does; the faster runs show what the code costs.
 */
function timing(fn: () => void, runs: number): number {
    for (let i = 0; i < 20; i++) fn();
    const times: number[] = [];
    for (let i = 0; i < runs; i++) {
        const start = performance.now();
        fn();
        times.push(performance.now() - start);
    }
    times.sort((a, b) => a - b);
    return times[Math.floor(times.length / 4)];
}

// What keeps edits fast is structural sharing: an edit copies only the path
// to what changed. That is asserted exactly below; the timings are loose
// smoke bounds only, because wall time on a shared runner is not reliable.
describe('engine cost on a 200-question form', () => {
    const form = form200();
    const ids = questionIds(form).slice(0, 200);
    const pages = pageIds(form);

    it('copies only the edited question and its page for one update_field', () => {
        const fieldId = ids[37];
        const out = applyOps(form, [{ op: 'update_field', fieldId, patch: { title: 'Changed' } }]);
        const before = form.fields as any[];
        const after = out.doc.fields as any[];
        expect(after).toHaveLength(before.length);
        let changedPages = 0;
        let changedQuestions = 0;
        before.forEach((page, i) => {
            if (after[i] === page) return;
            changedPages += 1;
            const oldFields = page.properties?.fields ?? [];
            const newFields = after[i].properties?.fields ?? [];
            oldFields.forEach((field: any, j: number) => {
                if (newFields[j] !== field) changedQuestions += 1;
            });
        });
        expect(changedPages).toBe(1);
        expect(changedQuestions).toBe(1);
        expect(out.inverse).toHaveLength(1);
    });

    it('applies one update_field and builds its inverse quickly (smoke bound)', () => {
        let n = 0;
        const time = timing(() => {
            const out = applyOps(form, [{ op: 'update_field', fieldId: ids[n++ % ids.length], patch: { title: `Title ${n}` } }]);
            if (out.inverse.length !== 1) throw new Error('expected one inverse op');
        }, 200);
        expect(time).toBeLessThan(5);
    });

    it('applies a 200-op batch (with its inverse) quickly (smoke bound)', () => {
        const ops: FormOp[] = ids.map((fieldId, i) =>
            i % 4 === 0
                ? { op: 'update_field', fieldId, patch: { title: `T${i}`, required: true } }
                : i % 4 === 1
                  ? { op: 'set_field_validation', fieldId, validation: { required: false } }
                  : i % 4 === 2
                    ? { op: 'move_field', fieldId, index: 0 }
                    : { op: 'add_field', pageId: pages[i % pages.length], field: { title: `New ${i}`, type: 'short_text' } }
        );
        expect(ops).toHaveLength(200);
        const time = timing(() => {
            const out = applyOps(form, ops, { newId: idMaker() });
            if (!out.results.every((r) => r.ok)) throw new Error('every op should apply');
        }, 40);
        expect(time).toBeLessThan(500);
    });
});

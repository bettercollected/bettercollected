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

describe('engine speed on a 200-question form', () => {
    const form = form200();
    const ids = questionIds(form).slice(0, 200);
    const pages = pageIds(form);

    it('applies one update_field and builds its inverse in under 0.3 ms', () => {
        let n = 0;
        const time = timing(() => {
            const out = applyOps(form, [{ op: 'update_field', fieldId: ids[n++ % ids.length], patch: { title: `Title ${n}` } }]);
            if (out.inverse.length !== 1) throw new Error('expected one inverse op');
        }, 200);
        expect(time).toBeLessThan(0.3);
    });

    it('applies a 200-op batch (with its inverse) in under 20 ms', () => {
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
        expect(time).toBeLessThan(20);
    });
});

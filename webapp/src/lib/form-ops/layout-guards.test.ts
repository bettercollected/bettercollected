// Layout containers: what the ops engine refuses so that no save is left with
// an invalid layout (a move that breaks a container's rule, ids that clash with
// a question's, a rule with too many conditions). The shared cases are in
// docs/spec/form-ops-v1.cases.json and docs/spec/layout-containers.cases.json.
import { describe, expect, it } from 'vitest';

import { CONTAINER_CONDITIONS_MAX, containerProblems, formItemIds, layoutProblems, reservedIds } from '@app/utils/layout-containers';

import { idMaker } from './__fixtures__/forms';
import { applyOps } from './apply';
import type { FormDoc, FormOp } from './types';

const q = (id: string) => ({ id, index: 0, type: 'short_text', title: id.toUpperCase() });
const RULE_ON_A = { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'a', fieldType: 'short_text', comparison: 'IS_EQUAL', value: 'x' }] };
const doc = (...pages: any[]): FormDoc =>
    ({
        title: 'T',
        builderVersion: 'v2',
        fields: pages.map((page, i) => ({
            id: `p${i + 1}`,
            index: i,
            type: 'slide',
            properties: Array.isArray(page) ? { fields: page.map((f, n) => ({ ...f, index: n })) } : { ...page, fields: page.fields.map((f: any, n: number) => ({ ...f, index: n })) }
        }))
    }) as any;
const run = (form: FormDoc, ops: any[], atomic = false) => applyOps(form, ops as FormOp[], { atomic, newId: idMaker() });
const order = (form: FormDoc, page = 0) => form.fields[page].properties!.fields!.map((f) => f.id);

const guarded = () => doc({ fields: ['a', 'b', 'c', 'd', 'e'].map(q), containers: [{ id: 'c1', type: 'panel', title: 'C1', fields: ['c', 'd'], logic: structuredClone(RULE_ON_A) }] });

describe('a move that would break a container rule', () => {
    it('is refused and leaves the document as it was (move_field)', () => {
        const before = guarded();
        for (const [index, text] of [
            [4, "A container's rule can only read questions before the container."],
            [2, "A container's rule cannot read one of its own questions."]
        ] as const) {
            const { doc: after, results } = run(before, [{ op: 'move_field', fieldId: 'a', index }], true);
            expect(results[0].ok).toBe(false);
            expect(results[0].message).toBe(`Moving 'A' there would break a layout container: ${text}`);
            expect(after).toBe(before);
        }
    });

    it('does not stop a partial batch, nor a move the rule does not care about', () => {
        const { doc: after, results } = run(guarded(), [
            { op: 'move_field', fieldId: 'a', index: 4 },
            { op: 'move_field', fieldId: 'b', index: 4 }
        ]);
        expect(results.map((r) => r.ok)).toEqual([false, true]);
        expect(order(after)).toEqual(['a', 'c', 'd', 'e', 'b']);
        expect(after.fields[0].properties!.containers![0].fields).toEqual(['c', 'd']);
        // out of the container: it keeps its rule and the remaining question
        const out = run(guarded(), [{ op: 'move_field', fieldId: 'd', index: 0 }]);
        expect(out.results[0].ok).toBe(true);
        expect(out.doc.fields[0].properties!.containers![0].fields).toEqual(['c']);
    });

    it('is not blamed for a problem the form already had', () => {
        const form = guarded();
        (form.fields[0].properties!.containers![0].logic!.conditions as any[]).push({ fieldId: 'gone', comparison: 'IS_EQUAL', value: 'x' });
        expect(layoutProblems(form.fields as any).length).toBeGreaterThan(0);
        expect(run(form, [{ op: 'move_field', fieldId: 'b', index: 4 }]).results[0].ok).toBe(true);
    });

    it('is refused for a page move too', () => {
        const form = doc([q('a')], { fields: [q('b'), q('c')], containers: [{ id: 'c1', type: 'panel', title: 'C1', fields: ['b', 'c'], logic: RULE_ON_A }] }, [q('z')]);
        for (const [pageId, index] of [
            ['p1', 2],
            ['p2', 0]
        ] as const) {
            const { doc: after, results } = run(form, [{ op: 'move_page', pageId, index }], true);
            expect(results[0].ok).toBe(false);
            expect(results[0].message).toMatch(/^Moving that page would break a layout container: /);
            expect(after).toBe(form);
        }
        expect(run(form, [{ op: 'move_page', pageId: 'p3', index: 0 }]).results[0].ok).toBe(true);
    });
});

describe('container and tab ids', () => {
    it('are never the id of a question, group child or page', () => {
        const page = { fields: [q('a'), q('b'), q('c1')], containers: [{ id: 'c1', type: 'panel', title: 'C1', fields: ['a', 'b'] }] };
        expect(layoutProblems(doc(page).fields as any).map((p) => p.message)).toEqual(["The id 'c1' is also the id of a question or page."]);
        const group = { id: 'g', type: 'group', title: 'People', properties: { repeat: { minItems: 1, maxItems: 3 }, fields: [q('t1')] } };
        const tabsPage = { fields: [q('a'), group], containers: [{ id: 'k', type: 'tabs', tabs: [{ id: 't1', title: 'One', fields: ['a'] }] }] };
        expect(layoutProblems(doc(tabsPage).fields as any).map((p) => p.message)).toEqual(["The id 't1' is also the id of a question or page."]);
        const pageId = doc({ fields: [q('a'), q('b')], containers: [{ id: 'p2', type: 'panel', title: 'P', fields: ['a', 'b'] }] }, [q('x')]);
        expect(layoutProblems(pageId.fields as any).map((p) => p.message)).toEqual(["The id 'p2' is also the id of a question or page."]);
        // a page alone is checked against its own ids when none are given
        expect(containerProblems(doc(page).fields[0] as any).length).toBe(1);
    });

    it('are refused by set_page_containers, and made-up ones skip them', () => {
        const form = doc([q('c1'), q('t1'), q('x')]);
        const refused = run(form, [{ op: 'set_page_containers', pageId: 'p1', containers: [{ id: 'x', type: 'panel', title: 'X', fields: ['c1'] }] }], true);
        expect(refused.results[0].message).toBe("The id 'x' is also the id of a question or page.");
        const { doc: after, results } = run(form, [
            {
                op: 'set_page_containers',
                pageId: 'p1',
                containers: [
                    {
                        type: 'tabs',
                        tabs: [
                            { title: 'One', fields: ['c1'] },
                            { title: 'Two', fields: ['t1'] }
                        ]
                    },
                    { type: 'panel', title: 'Rest', fields: ['x'] }
                ]
            }
        ]);
        expect(results[0].ok).toBe(true);
        const containers = after.fields[0].properties!.containers!;
        expect(containers.map((c) => c.id)).toEqual(['c2', 'c3']);
        expect(containers[0].tabs!.map((t) => t.id)).toEqual(['t2', 't3']);
        expect(layoutProblems(after.fields as any)).toEqual([]);
    });

    it('are not minted over a question when a page is copied or the builder adds one', () => {
        const form = doc({ fields: [q('a'), q('b')], containers: [{ id: 'c1', type: 'panel', title: 'C1', fields: ['a', 'b'] }] }, [q('c2')]);
        const copied = run(form, [{ op: 'duplicate_page', pageId: 'p1' }]);
        expect(copied.results[0].ok).toBe(true);
        expect(copied.doc.fields[1].properties!.containers![0].id).toBe('c3');
        expect(layoutProblems(copied.doc.fields as any)).toEqual([]);
        expect([...reservedIds(form.fields as any)].sort()).toEqual(['a', 'b', 'c1', 'c2', 'p1', 'p2']);
        expect([...formItemIds(form.fields as any)].sort()).toEqual(['a', 'b', 'c2', 'p1', 'p2']);
    });
});

describe('the size of a container rule', () => {
    const rule = (n: number) => ({ action: 'SHOW', operator: 'OR', conditions: Array.from({ length: n }, (_, i) => ({ fieldId: 'a', comparison: 'IS_EQUAL', value: String(i) })) });
    const panel = (n: number) => ({ op: 'set_page_containers', pageId: 'p1', containers: [{ type: 'panel', title: 'T', fields: ['b', 'c'], logic: rule(n) }] });

    it('has a cap of twenty conditions in the engine and in the structure check', () => {
        const form = doc([q('a'), q('b'), q('c')]);
        expect(CONTAINER_CONDITIONS_MAX).toBe(20);
        expect(run(form, [panel(20)]).results[0].ok).toBe(true);
        const refused = run(form, [panel(21)], true);
        expect(refused.results[0].message).toBe("A container's rule can have at most 20 conditions.");
        const page = doc({ fields: [q('a'), q('b'), q('c')], containers: [{ id: 'c1', type: 'panel', title: 'T', fields: ['b', 'c'], logic: rule(21) }] }).fields[0] as any;
        expect(containerProblems(page).map(([, message]) => message)).toEqual(["A container's rule can have at most 20 conditions."]);
    });
});

import { describe, expect, it } from 'vitest';

import { applyOps } from './apply';
import type { FormDoc } from './types';

const q = (id: string, extra: Record<string, unknown> = {}) => ({ id, index: 0, type: 'short_text', title: id, ...extra }) as any;
const form = (): FormDoc =>
    ({
        title: 'Form',
        builderVersion: 'v2',
        fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields: [q('a'), q('b', { properties: { logic: { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'a', comparison: 'IS_NOT_EMPTY', fieldType: 'short_text' }] } } }), q('c')] } }]
    }) as any;

const ids = (doc: FormDoc) => ((doc.fields![0].properties!.fields as any[]) ?? []).map((f) => f.id);

describe('splice_fields', () => {
    it('inserts at an index and is undone by its inverse', () => {
        const before = form();
        const done = applyOps(before, [{ op: 'splice_fields', pageId: 'p1', index: 1, fields: [q('n1'), q('n2')] }] as any, { atomic: true });
        expect(done.results.every((r) => r.ok)).toBe(true);
        expect(ids(done.doc)).toEqual(['a', 'n1', 'n2', 'b', 'c']);
        expect(done.createdIds).toEqual(['n1', 'n1', 'n2']);
        // the inverse puts the form back
        const back = applyOps(done.doc, done.inverse, { atomic: true });
        expect(back.results.every((r) => r.ok)).toBe(true);
        expect(ids(back.doc)).toEqual(['a', 'b', 'c']);
    });

    it('replaces a copy in place, keeping the id it is given, and drops what read a question that went', () => {
        const done = applyOps(form(), [{ op: 'splice_fields', pageId: 'p1', index: 0, replaceIds: ['a', 'b'], fields: [q('a', { title: 'A2' })] }] as any, { atomic: true });
        expect(done.results[0].ok).toBe(true);
        expect(ids(done.doc)).toEqual(['a', 'c']);
        expect((done.doc.fields![0].properties!.fields as any[])[0].title).toBe('A2');
    });

    it('refuses a used id, a question of another page and an empty splice, and changes nothing', () => {
        const doc = form();
        const used = applyOps(doc, [{ op: 'splice_fields', pageId: 'p1', fields: [q('a')] }] as any, { atomic: true });
        expect(used.results[0].message).toContain('already used');
        expect(used.doc).toBe(doc);
        expect(applyOps(doc, [{ op: 'splice_fields', pageId: 'p1', replaceIds: ['zzz'], fields: [] }] as any, { atomic: true }).results[0].message).toContain('is not a question of page');
        expect(applyOps(doc, [{ op: 'splice_fields', pageId: 'p1', fields: [] }] as any, { atomic: true }).results[0].message).toContain('needs questions');
    });

    it('is for the builder only', () => {
        const refused = applyOps(form(), [{ op: 'splice_fields', pageId: 'p1', fields: [q('n')] }] as any, { editor: false });
        expect(refused.results[0].ok).toBe(false);
        expect(refused.results[0].message).toContain('only available in the form editor');
    });
});

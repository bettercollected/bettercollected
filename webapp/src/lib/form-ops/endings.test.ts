/**
 * Ending ops in the TypeScript engine: the backend's semantics (the shared
 * corpus checks the forms and messages case by case) and undo.
 */
import { describe, expect, it } from 'vitest';

import { idMaker, smallForm } from './__fixtures__/forms';
import { applyOps } from './apply';
import type { FormDoc, FormOp } from './types';

const ids = (doc: FormDoc) => (doc.thankyouPage ?? []).map((e) => e.id);
const defaults = (doc: FormDoc) => (doc.thankyouPage ?? []).map((e) => !!e.isDefault);
const jumpOn = (fieldId: string, extra: Record<string, any> = {}) => ({ target: '__SUBMIT__', conditions: [{ fieldId, comparison: 'IS_EMPTY' as const }], ...extra });

describe('ending ops', () => {
    it('add_ending with a ref, and a jump to it in the same batch', () => {
        const { doc, results } = applyOps(
            smallForm(),
            [
                { op: 'add_ending', ref: 'late', name: ' Late ', title: 'Later', index: 0 },
                { op: 'set_page_jumps', pageId: 'p1', jumps: [jumpOn('name', { endingId: '$ref:late' })] }
            ] as FormOp[],
            { newId: idMaker('n') }
        );
        expect(results.map((r) => r.ok)).toEqual([true, true]);
        expect(results[0].message).toBe("Added the ending 'Late'");
        const created = results[0].createdId!;
        expect(ids(doc)).toEqual([created, 'thanks', 'sorry']);
        expect(doc.thankyouPage![0]).toEqual({ id: created, name: 'Late', title: 'Later', layout: 'SINGLE_COLUMN_NO_BACKGROUND' });
        expect((doc.fields![0].properties!.jumps as any[])[0].endingId).toBe(created);
    });

    it('isDefault: true moves the default, false unmarks only that ending', () => {
        const start = smallForm(); // 'sorry' is the default
        let out = applyOps(start, [{ op: 'update_ending', endingId: 'thanks', patch: { isDefault: false } }] as FormOp[]);
        expect(defaults(out.doc)).toEqual([false, true]);
        out = applyOps(start, [{ op: 'add_ending', title: 'x', isDefault: false }] as FormOp[]);
        expect(defaults(out.doc)).toEqual([false, true, false]);
        out = applyOps(start, [{ op: 'update_ending', endingId: 'thanks', patch: { isDefault: true } }] as FormOp[]);
        expect(defaults(out.doc)).toEqual([true, false]);
        expect(out.results[0].message).toBe("Updated the ending 'Thanks' (default)");
        out = applyOps(start, [{ op: 'update_ending', endingId: 'sorry', patch: { isDefault: false } }] as FormOp[]);
        expect(defaults(out.doc)).toEqual([false, false]);
    });

    it('limits: 20 endings, text lengths, link and id pattern', () => {
        const many = { ...smallForm(), thankyouPage: Array.from({ length: 20 }, (_, i) => ({ id: `e${i}` })) };
        expect(applyOps(many, [{ op: 'add_ending' }] as FormOp[]).results[0].message).toBe('A form can have at most 20 endings.');
        const refused = (op: any) => applyOps(smallForm(), [op] as FormOp[]).results[0];
        expect(refused({ op: 'add_ending', buttonText: 'b'.repeat(81) }).message).toBe("An ending's button text can be at most 80 characters.");
        expect(refused({ op: 'update_ending', endingId: 'thanks', patch: { buttonLink: 'ftp://x' } }).message).toBe("The ending button's link must be an http(s) URL.");
        expect(refused({ op: 'set_endings', endings: [{ id: '<x>' }] }).message).toContain('String should match pattern');
        // a refused patch changes nothing
        const partial = applyOps(smallForm(), [{ op: 'update_ending', endingId: 'thanks', patch: { title: 'New', message: 'm'.repeat(5001) } }] as FormOp[]);
        expect(partial.doc.thankyouPage![0].title).toBe('Thanks');
    });

    it('remove_ending sends its jumps to the default ending, and the last one stays', () => {
        const withJump = applyOps(smallForm(), [{ op: 'set_page_jumps', pageId: 'p1', jumps: [jumpOn('name', { endingId: 'thanks' })] }] as FormOp[]).doc;
        const { doc, results } = applyOps(withJump, [{ op: 'remove_ending', endingId: 'thanks' }] as FormOp[]);
        expect(results[0].message).toBe("Removed the ending 'Thanks' (and 1 jump(s) to it now show the default ending)");
        expect(ids(doc)).toEqual(['sorry']);
        const jump = (doc.fields![0].properties!.jumps as any[])[0];
        expect(jump.target).toBe('__SUBMIT__');
        expect(jump).not.toHaveProperty('endingId');
        expect(applyOps(doc, [{ op: 'remove_ending', endingId: 'sorry' }] as FormOp[]).results[0].message).toBe('A form keeps at least one ending; change this one instead.');
    });

    it('endings stored without ids get them when an op changes the list', () => {
        const legacy = { ...smallForm(), thankyouPage: [{ title: 'A' }, { title: 'B' }] };
        const { doc } = applyOps(legacy, [{ op: 'update_ending', endingId: 'ending-2', patch: { name: 'Second' } }] as FormOp[]);
        expect(ids(doc)).toEqual(['ending-1', 'ending-2']);
        // and undo gives back the list as it was, without ids
        const back = applyOps(doc, applyOps(legacy, [{ op: 'update_ending', endingId: 'ending-2', patch: { name: 'Second' } }] as FormOp[]).inverse);
        expect(back.doc).toEqual(legacy);
    });

    it('undo and redo take every ending op back, jumps included', () => {
        const start = applyOps(smallForm(), [{ op: 'set_page_jumps', pageId: 'p1', jumps: [jumpOn('name', { endingId: 'thanks' })] }] as FormOp[]).doc;
        const batches: FormOp[][] = [
            [
                { op: 'add_ending', ref: 'n', title: 'New', isDefault: true },
                { op: 'set_page_jumps', pageId: 'p2', jumps: [jumpOn('bio', { endingId: '$ref:n' })] }
            ] as FormOp[],
            [{ op: 'update_ending', endingId: 'thanks', patch: { name: 'Eligible', message: '', buttonText: 'Go', isDefault: true } }] as FormOp[],
            [{ op: 'remove_ending', endingId: 'thanks' }] as FormOp[],
            [{ op: 'set_endings', endings: [{ id: 'sorry', title: 'Only' }] }] as FormOp[]
        ];
        for (const ops of batches) {
            const { doc, inverse, results } = applyOps(start, ops, { newId: idMaker('u') });
            expect(results.every((r) => r.ok)).toBe(true);
            const undone = applyOps(doc, inverse, { atomic: true });
            expect(undone.results.filter((r) => !r.ok)).toEqual([]);
            expect(undone.doc).toEqual(start);
            expect(applyOps(undone.doc, undone.inverse, { atomic: true }).doc).toEqual(doc);
        }
    });
});

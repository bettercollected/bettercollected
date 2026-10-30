import { beforeEach, describe, expect, it } from 'vitest';

import { forgetResponseList, forgetResponseListOutside, rememberResponseListPage, rememberResponseListView, rememberedListView, rememberedNeighbours } from './response-list-memory';

const page = (n: number, ids: string[], extra: Partial<{ size: number; total: number }> = {}) => ({ page: n, size: 3, total: 9, ids, ...extra });
const key = (formId = 'f1', searchText = '', workspaceId = 'w1') => ({ workspaceId, formId, searchText });
const ids = ({ previousId, nextId }: { previousId?: string; nextId?: string }) => ({ previousId, nextId });

describe('remembered response list', () => {
    beforeEach(() => forgetResponseList());

    it('knows nothing before a list was seen, or for a response not in it', () => {
        expect(rememberedNeighbours('w1', 'f1', 'r2')).toEqual({});
        rememberResponseListPage(key(), page(1, ['r1', 'r2', 'r3']));
        expect(rememberedNeighbours('w1', 'f1', 'zzz')).toEqual({});
    });

    it('gives the neighbours within a page and none past its ends without the next page', () => {
        rememberResponseListPage(key(), page(2, ['r4', 'r5', 'r6']));
        expect(ids(rememberedNeighbours('w1', 'f1', 'r5'))).toEqual({ previousId: 'r4', nextId: 'r6' });
        expect(ids(rememberedNeighbours('w1', 'f1', 'r4'))).toEqual({ previousId: undefined, nextId: 'r5' });
        expect(ids(rememberedNeighbours('w1', 'f1', 'r6'))).toEqual({ previousId: 'r5', nextId: undefined });
    });

    it('gives the place of the response in the whole list', () => {
        rememberResponseListPage(key(), page(2, ['r4', 'r5', 'r6']));
        expect(rememberedNeighbours('w1', 'f1', 'r5')).toMatchObject({ position: 5, total: 9 });
    });

    it('joins consecutive pages seen, never pages with a gap', () => {
        rememberResponseListPage(key(), page(1, ['r1', 'r2', 'r3']));
        rememberResponseListPage(key(), page(2, ['r4', 'r5', 'r6']));
        rememberResponseListPage(key(), page(4, ['r10', 'r11', 'r12'], { total: 9 }));
        expect(ids(rememberedNeighbours('w1', 'f1', 'r3'))).toEqual({ previousId: 'r2', nextId: 'r4' });
        expect(rememberedNeighbours('w1', 'f1', 'r4').previousId).toBe('r3');
        expect(rememberedNeighbours('w1', 'f1', 'r6').nextId).toBeUndefined();
        expect(rememberedNeighbours('w1', 'f1', 'r10').previousId).toBeUndefined();
    });

    it('starts again for another form, page size or total', () => {
        rememberResponseListPage(key(), page(1, ['r1', 'r2', 'r3']));
        rememberResponseListPage(key(), page(2, ['r4', 'r5', 'r6'], { total: 5 }));
        expect(rememberedNeighbours('w1', 'f1', 'r3').nextId).toBeUndefined();
        expect(rememberedNeighbours('w1', 'f1', 'r1')).toEqual({});
        rememberResponseListPage(key('f2'), page(1, ['x1', 'x2']));
        expect(rememberedNeighbours('w1', 'f1', 'r4')).toEqual({});
        expect(ids(rememberedNeighbours('w1', 'f2', 'x1'))).toEqual({ previousId: undefined, nextId: 'x2' });
    });

    it('keeps the same form id in another workspace apart (an imported form can be in two)', () => {
        rememberResponseListPage(key('f1', '', 'w1'), page(1, ['r1', 'r2', 'r3']));
        expect(rememberedNeighbours('w2', 'f1', 'r2')).toEqual({});
        rememberResponseListPage(key('f1', '', 'w2'), page(2, ['r4', 'r5', 'r6']));
        // the first workspace's page is not joined to the second's
        expect(rememberedNeighbours('w2', 'f1', 'r4').previousId).toBeUndefined();
        expect(rememberedNeighbours('w1', 'f1', 'r2')).toEqual({});
    });

    it('never joins the pages of two searches, even with the same total and page size', () => {
        rememberResponseListPage(key('f1', 'anna'), page(1, ['r1', 'r2', 'r3']));
        rememberResponseListPage(key('f1', 'bram'), page(2, ['r7', 'r8', 'r9']));
        expect(rememberedNeighbours('w1', 'f1', 'r7').previousId).toBeUndefined();
        expect(rememberedNeighbours('w1', 'f1', 'r3')).toEqual({});
    });

    it('starts again when the search changes, before the new results are shown', () => {
        rememberResponseListPage(key(), page(1, ['r1', 'r2', 'r3']));
        rememberResponseListView(key('f1', 'zzz'), 1);
        expect(rememberedNeighbours('w1', 'f1', 'r2')).toEqual({});
        expect(rememberedListView('w1', 'f1')).toEqual({ page: 1, searchText: 'zzz' });
    });

    it('remembers the page and the search the list was left on, for that workspace and form only', () => {
        expect(rememberedListView('w1', 'f1')).toBeNull();
        rememberResponseListView(key('f1', 'anna'), 1);
        rememberResponseListPage(key('f1', 'anna'), page(3, ['r7', 'r8', 'r9']));
        expect(rememberedListView('w1', 'f1')).toEqual({ page: 3, searchText: 'anna' });
        rememberResponseListView(key('f1', 'anna'), 2);
        expect(rememberedListView('w1', 'f1')).toEqual({ page: 2, searchText: 'anna' });
        expect(rememberedListView('w2', 'f1')).toBeNull();
        expect(rememberedListView('w1', 'f2')).toBeNull();
    });

    it('forgets the list when another workspace opens, and keeps it in the same one', () => {
        rememberResponseListView(key('f1', 'anna@example.com'), 2);
        rememberResponseListPage(key('f1', 'anna@example.com'), page(2, ['r4', 'r5', 'r6']));
        forgetResponseListOutside('w1');
        expect(rememberedListView('w1', 'f1')).toEqual({ page: 2, searchText: 'anna@example.com' });
        forgetResponseListOutside('w2');
        // back in the first workspace: nothing of that list (or its search) is left
        expect(rememberedListView('w1', 'f1')).toBeNull();
        expect(rememberedNeighbours('w1', 'f1', 'r5')).toEqual({});
    });

    it('keeps only ids and counts for the page: no answers, no search text', () => {
        rememberResponseListPage(key('f1', 'anna@example.com'), page(1, ['r1', 'r2'], { total: 2, size: 50 }));
        expect(JSON.stringify(rememberedNeighbours('w1', 'f1', 'r1'))).toBe('{"nextId":"r2","position":1,"total":2}');
    });
});

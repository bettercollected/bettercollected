import { beforeEach, describe, expect, it } from 'vitest';

import { forgetResponseList, rememberResponseListPage, rememberedNeighbours } from './response-list-memory';

const page = (n: number, ids: string[], extra: Partial<{ size: number; total: number }> = {}) => ({ page: n, size: 3, total: 9, ids, ...extra });

describe('remembered response list', () => {
    beforeEach(() => forgetResponseList());

    it('knows nothing before a list was seen, or for a response not in it', () => {
        expect(rememberedNeighbours('f1', 'r2')).toEqual({});
        rememberResponseListPage('f1', page(1, ['r1', 'r2', 'r3']));
        expect(rememberedNeighbours('f1', 'zzz')).toEqual({});
    });

    it('gives the neighbours within a page and none past its ends without the next page', () => {
        rememberResponseListPage('f1', page(2, ['r4', 'r5', 'r6']));
        expect(rememberedNeighbours('f1', 'r5')).toEqual({ previousId: 'r4', nextId: 'r6' });
        expect(rememberedNeighbours('f1', 'r4')).toEqual({ previousId: undefined, nextId: 'r5' });
        expect(rememberedNeighbours('f1', 'r6')).toEqual({ previousId: 'r5', nextId: undefined });
    });

    it('joins consecutive pages seen, never pages with a gap', () => {
        rememberResponseListPage('f1', page(1, ['r1', 'r2', 'r3']));
        rememberResponseListPage('f1', page(2, ['r4', 'r5', 'r6']));
        rememberResponseListPage('f1', page(4, ['r10', 'r11', 'r12'], { total: 9 }));
        expect(rememberedNeighbours('f1', 'r3')).toEqual({ previousId: 'r2', nextId: 'r4' });
        expect(rememberedNeighbours('f1', 'r4').previousId).toBe('r3');
        expect(rememberedNeighbours('f1', 'r6').nextId).toBeUndefined();
        expect(rememberedNeighbours('f1', 'r10').previousId).toBeUndefined();
    });

    it('starts again for another form, page size or total (another search)', () => {
        rememberResponseListPage('f1', page(1, ['r1', 'r2', 'r3']));
        rememberResponseListPage('f1', page(2, ['r4', 'r5', 'r6'], { total: 5 }));
        expect(rememberedNeighbours('f1', 'r3').nextId).toBeUndefined();
        expect(rememberedNeighbours('f1', 'r1')).toEqual({});
        rememberResponseListPage('f2', page(1, ['x1', 'x2']));
        expect(rememberedNeighbours('f1', 'r4')).toEqual({});
        expect(rememberedNeighbours('f2', 'x1')).toEqual({ previousId: undefined, nextId: 'x2' });
    });

    it('keeps only ids: nothing else is held', () => {
        rememberResponseListPage('f1', page(1, ['r1', 'r2']));
        expect(JSON.stringify(rememberedNeighbours('f1', 'r1'))).toBe('{"nextId":"r2"}');
    });
});

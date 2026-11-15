import { describe, expect, it } from 'vitest';

import { PIGMENTS, fnv1a32, formHueIndex, formPigment } from './form-hue';

describe('the hash behind a form hue', () => {
    it('is 32-bit FNV-1a (published test vectors)', () => {
        expect(fnv1a32('')).toBe(0x811c9dc5);
        expect(fnv1a32('a')).toBe(0xe40c292c);
        expect(fnv1a32('foobar')).toBe(0xbf9cf968);
    });

    it('hashes the UTF-8 bytes, not the UTF-16 units', () => {
        // U+00FC is the two bytes c3 bc; FNV-1a over those two bytes (computed
        // outside JavaScript) is what a server or another client would get
        expect(fnv1a32('ü')).toBe(0x119dd44a);
    });

    it('always returns an unsigned 32-bit integer', () => {
        for (const text of ['', 'a', 'foobar', 'x'.repeat(500), '\u{1F600}']) {
            const hash = fnv1a32(text);
            expect(Number.isInteger(hash)).toBe(true);
            expect(hash).toBeGreaterThanOrEqual(0);
            expect(hash).toBeLessThanOrEqual(0xffffffff);
        }
    });
});

describe('the pigments', () => {
    it('are five, in this order (the order is part of what every form looks like)', () => {
        expect([...PIGMENTS]).toEqual(['tomato', 'sun', 'mint', 'sky', 'orchid']);
    });
});

// Written once from an independent implementation and never edited: changing
// an expected value here recolours every form in every workspace.
const PINNED: ReadonlyArray<readonly [string, number]> = [
    ['0b6f2c1e-8a4d-4f3b-9c52-7d1e6a3f5b90', 3],
    ['f47ac10b-58cc-4372-a567-0e02b2c3d479', 2],
    ['6c84fb90-12c4-11e1-840d-7b25c5ee775a', 1],
    ['9a1de644-815e-4d3e-b7f1-2c0f4e8a6d13', 4],
    ['a3c1e5f7-2b4d-4968-8ab0-c1d2e3f40516', 0],
    ['650f1a2b3c4d5e6f7a8b9c0d', 4],
    ['507f1f77bcf86cd799439011', 3],
    ['64b7e9a0c1d2e3f4a5b6c7d8', 4],
    ['5f8d0d55b54764421b7156c3', 2],
    ['F47AC10B-58CC-4372-A567-0E02B2C3D479', 2],
    ['507F1F77BCF86CD799439011', 3],
    ['  0b6f2c1e-8a4d-4f3b-9c52-7d1e6a3f5b90  ', 3],
    ['form-intake-2026', 3],
    ['Ünï-cödé-ïd', 3]
];

describe('the hue of a form', () => {
    it.each(PINNED)('is pinned for %j', (id, index) => {
        expect(formHueIndex(id)).toBe(index);
        expect(formPigment(id)).toBe(PIGMENTS[index]);
    });

    it('does not depend on letter case or surrounding spaces', () => {
        const id = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';
        expect(formHueIndex(id.toUpperCase())).toBe(formHueIndex(id));
        expect(formHueIndex(`  ${id}\n`)).toBe(formHueIndex(id));
        expect(formPigment(id.toUpperCase())).toBe(formPigment(id));
    });

    it('is the same on every call', () => {
        const id = '507f1f77bcf86cd799439011';
        const first = formHueIndex(id);
        for (let i = 0; i < 50; i++) {
            expect(formHueIndex(id)).toBe(first);
        }
    });

    it('is a whole number from 0 to 4 for any text, including an empty id', () => {
        for (const id of ['', ' ', 'a', '\u{1F600}', 'x'.repeat(1000)]) {
            const index = formHueIndex(id);
            expect(Number.isInteger(index)).toBe(true);
            expect(index).toBeGreaterThanOrEqual(0);
            expect(index).toBeLessThan(PIGMENTS.length);
            expect(PIGMENTS).toContain(formPigment(id));
        }
    });

    it('spreads ids over the five hues, whatever shape the ids have', () => {
        // a small deterministic generator, so the test never changes between runs
        let seed = 123456789;
        const next = () => {
            seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
            return seed;
        };
        const hex = (digits: number) => Array.from({ length: digits }, () => (next() >>> 28).toString(16)).join('');
        const shapes: Array<[string, (i: number) => string]> = [
            ['uuid', () => `${hex(8)}-${hex(4)}-4${hex(3)}-a${hex(3)}-${hex(12)}`],
            ['random object ids', () => hex(24)],
            // object ids made in one second differ only in their counter: the worst case for a weak hash
            ['sequential object ids', (i) => `507f1f77bcf86cd7${(0x99439011 + i).toString(16).padStart(8, '0')}`]
        ];
        const total = 10000;
        for (const [shape, make] of shapes) {
            const counts = new Array(PIGMENTS.length).fill(0);
            for (let i = 0; i < total; i++) {
                counts[formHueIndex(make(i))]++;
            }
            const expected = total / PIGMENTS.length;
            for (const count of counts) {
                expect(count, `${shape}: ${counts.join(', ')}`).toBeGreaterThanOrEqual(expected * 0.9);
                expect(count, `${shape}: ${counts.join(', ')}`).toBeLessThanOrEqual(expected * 1.1);
            }
        }
    });
});

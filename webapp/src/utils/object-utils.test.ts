import { describe, expect, it } from 'vitest';

import { deepCopy } from './object-utils';

describe('deepCopy', () => {
    it('arrays stay arrays (the `{...array}` editor-crash class)', () => {
        const copy = deepCopy([{ id: 'a' }, { id: 'b' }]);
        expect(Array.isArray(copy)).toBe(true);
        expect(typeof (copy as any).some).toBe('function');
        expect(copy).toHaveLength(2);
    });

    it('nested structures are fully detached from the source', () => {
        const src = { slides: [{ id: 's1', properties: { fields: [{ id: 'q1' }] } }] };
        const copy = deepCopy(src);
        copy.slides[0].properties.fields[0].id = 'mutated';
        expect(src.slides[0].properties.fields[0].id).toBe('q1');
    });

    it('primitives and null pass through', () => {
        expect(deepCopy(5)).toBe(5);
        expect(deepCopy('x')).toBe('x');
        expect(deepCopy(null)).toBeNull();
    });
});

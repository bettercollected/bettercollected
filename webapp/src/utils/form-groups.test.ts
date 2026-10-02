import { describe, expect, it } from 'vitest';

import { formGroupsAfterSave } from '@app/utils/form-groups';

const g = (id: string) => ({ id, name: id }) as any;

describe('formGroupsAfterSave', () => {
    it('keeps every group once, in order, and drops blanks', () => {
        expect(formGroupsAfterSave([g('a'), null, g('b'), g('a'), undefined, g('c')]).map((x) => x.id)).toEqual(['a', 'b', 'c']);
    });

    it('adding a form to one more group keeps the groups it was already in', () => {
        const existing = [g('a'), g('b')];
        expect(formGroupsAfterSave([...existing, g('c')]).map((x) => x.id)).toEqual(['a', 'b', 'c']);
        expect(formGroupsAfterSave([...existing, g('b')]).map((x) => x.id)).toEqual(['a', 'b']);
    });
});

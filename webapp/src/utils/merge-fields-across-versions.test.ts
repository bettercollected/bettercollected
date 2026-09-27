import { describe, expect, it } from 'vitest';

import { mergeFieldsAcrossVersions } from '@app/utils/form-builder-block-utils';

const field = (id: string, title = id) => ({ id, title }) as any;

describe('mergeFieldsAcrossVersions', () => {
    it("keeps the form's own fields first and adds fields only other versions have", () => {
        const current = [field('a'), field('b')];
        const older = [field('a'), field('old')];
        const newer = [field('b'), field('new'), field('old')];
        expect(mergeFieldsAcrossVersions(current, [older, newer]).map((f) => f.id)).toEqual(['a', 'b', 'old', 'new']);
    });

    it('returns the form fields unchanged when there are no other versions', () => {
        const current = [field('a')];
        expect(mergeFieldsAcrossVersions(current, [])).toEqual(current);
    });
});

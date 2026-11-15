import { describe, expect, it } from 'vitest';

import { isFormShareable } from './vvalidation-utils';

describe('isFormShareable', () => {
    it('is a published, open form that is not hidden', () => {
        expect(isFormShareable({ isPublished: true, settings: {} })).toBe(true);
        expect(isFormShareable({ isPublished: true, settings: { formCloseDate: '2999-01-01T00:00:00Z' } })).toBe(true);
    });

    it.each([
        ['a draft', { isPublished: false, settings: {} }],
        ['a hidden form', { isPublished: true, settings: { hidden: true } }],
        ['a form past its close date', { isPublished: true, settings: { formCloseDate: '2020-01-01T00:00:00Z' } }],
        ['no form', undefined]
    ])('is false for %s', (_name, form) => {
        expect(isFormShareable(form as any)).toBe(false);
    });

    it('treats a published form with no settings as open and visible', () => {
        expect(isFormShareable({ isPublished: true, settings: null })).toBe(true);
    });
});

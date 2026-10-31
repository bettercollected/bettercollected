import { describe, expect, it } from 'vitest';

import { isUnavailableForm, shownSlide } from './closed-form';

describe('a form that takes no responses', () => {
    it.each(['closed', 'not_yet_open', 'full'] as const)('is unavailable when it is %s, and shows its welcome page on every page', (reason) => {
        const form = { unavailable: reason };
        expect(isUnavailableForm(form)).toBe(true);
        for (const slide of [-1, 0, 1, 4]) expect(shownSlide(form, slide)).toBe(-1);
        // an ending already reached stays on screen
        expect(shownSlide(form, -2)).toBe(-2);
    });

    it('is available without a reason, and the place is kept', () => {
        for (const form of [{}, null, undefined, { unavailable: undefined }]) {
            expect(isUnavailableForm(form)).toBe(false);
            expect(shownSlide(form, 2)).toBe(2);
        }
    });
});

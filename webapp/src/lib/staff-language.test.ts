import { afterEach, describe, expect, it, vi } from 'vitest';

import { STAFF_LANGUAGE_STORAGE_KEY, asStaffLanguage, pickStaffLanguage, readChosenStaffLanguage, storeChosenStaffLanguage } from './staff-language';

describe('the staff language', () => {
    it('is Dutch for any Dutch browser language, English for the rest', () => {
        expect(pickStaffLanguage(null, ['nl'])).toBe('nl');
        expect(pickStaffLanguage(null, ['nl-NL'])).toBe('nl');
        expect(pickStaffLanguage(null, ['nl-BE', 'en-GB'])).toBe('nl');
        expect(pickStaffLanguage(null, ['en-US', 'nl'])).toBe('en');
        expect(pickStaffLanguage(null, ['de-DE', 'nl-NL'])).toBe('nl');
        expect(pickStaffLanguage(null, ['de-DE', 'fr'])).toBe('en');
        expect(pickStaffLanguage(null, [])).toBe('en');
    });

    it('is the person\'s own choice when there is one, whatever the browser prefers', () => {
        expect(pickStaffLanguage('en', ['nl-NL'])).toBe('en');
        expect(pickStaffLanguage('nl', ['en-GB'])).toBe('nl');
    });

    it('never uses anything that is not one of the two languages', () => {
        expect(asStaffLanguage('fr')).toBeNull();
        expect(asStaffLanguage('<script>')).toBeNull();
        expect(asStaffLanguage(undefined)).toBeNull();
        expect(pickStaffLanguage('fr', ['nl-NL'])).toBe('nl');
        expect(pickStaffLanguage({}, [])).toBe('en');
    });
});

describe('remembering the choice in this browser', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        window.localStorage.clear();
    });

    it('stores and reads it back', () => {
        expect(readChosenStaffLanguage()).toBeNull();
        storeChosenStaffLanguage('nl');
        expect(window.localStorage.getItem(STAFF_LANGUAGE_STORAGE_KEY)).toBe('nl');
        expect(readChosenStaffLanguage()).toBe('nl');
    });

    it('ignores a stored value that is not a language', () => {
        window.localStorage.setItem(STAFF_LANGUAGE_STORAGE_KEY, 'klingon');
        expect(readChosenStaffLanguage()).toBeNull();
    });

    it('does not break when storage is blocked: nothing is read, nothing is remembered', () => {
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        expect(readChosenStaffLanguage()).toBeNull();
        expect(() => storeChosenStaffLanguage('nl')).not.toThrow();
    });
});

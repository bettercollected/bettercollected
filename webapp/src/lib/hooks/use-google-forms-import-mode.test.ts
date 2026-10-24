import { describe, expect, it } from 'vitest';

import { googleFormsImportMode, googleFormsRefusal } from './use-google-forms-import-mode';

describe('Google Forms import mode', () => {
    it('reads the mode GET /providers reports for Google', () => {
        expect(googleFormsImportMode([{ providerName: 'google', importMode: 'on' }])).toBe('on');
        expect(googleFormsImportMode([{ providerName: 'google', importMode: 'readonly' }])).toBe('readonly');
        // a platform admin's list has no mode: imports as before
        expect(googleFormsImportMode([{ providerName: 'google' }])).toBe('on');
    });

    it('is off when Google is not listed, unknown without a list', () => {
        expect(googleFormsImportMode([])).toBe('off');
        expect(googleFormsImportMode([{ providerName: 'typeform' }])).toBe('off');
        expect(googleFormsImportMode(undefined)).toBeUndefined();
        expect(googleFormsImportMode(null)).toBeUndefined();
    });

    it("recognises the switch's refusals only", () => {
        expect(googleFormsRefusal({ status: 403, data: { code: 'google_forms_readonly', message: '...' } })).toBe('readonly');
        expect(googleFormsRefusal({ status: 410, data: { code: 'google_forms_off' } })).toBe('off');
        expect(googleFormsRefusal({ status: 403, data: 'Upgrade plan to import more forms' })).toBeNull();
        expect(googleFormsRefusal({ status: 410, data: { code: 'google_forms_readonly' } })).toBeNull();
        expect(googleFormsRefusal(undefined)).toBeNull();
    });
});

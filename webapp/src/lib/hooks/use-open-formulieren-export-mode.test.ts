import { describe, expect, it } from 'vitest';

import { openFormulierenExportOn } from './use-open-formulieren-export-mode';

describe('openFormulierenExportOn', () => {
    it('is on only for an entry whose exportMode is "on"', () => {
        expect(openFormulierenExportOn([{ providerName: 'open_formulieren', exportMode: 'on' }])).toBe(true);
        expect(
            openFormulierenExportOn([
                { providerName: 'google', importMode: 'on' },
                { providerName: 'open_formulieren', importMode: 'on', exportMode: 'on' }
            ])
        ).toBe(true);
    });

    it('is off for no entry, an import-only entry, an unknown mode or a list that could not be read', () => {
        expect(openFormulierenExportOn([])).toBe(false);
        expect(openFormulierenExportOn([{ providerName: 'open_formulieren', importMode: 'on' }])).toBe(false);
        expect(openFormulierenExportOn([{ providerName: 'open_formulieren', exportMode: 'readonly' }])).toBe(false);
        expect(openFormulierenExportOn([{ providerName: 'google', exportMode: 'on' }])).toBe(false);
        expect(openFormulierenExportOn(undefined)).toBe(false);
        expect(openFormulierenExportOn(null)).toBe(false);
        expect(openFormulierenExportOn([null, undefined])).toBe(false);
    });
});

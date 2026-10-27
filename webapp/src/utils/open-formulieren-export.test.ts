import { describe, expect, it } from 'vitest';

import { FALLBACK_EXPORT_FILE_NAME, exportFileName, exportRefusalIsTooLarge, openFormulierenExportOf, unmappedCount } from './open-formulieren-export';

describe('the Open Formulieren export download', () => {
    it('takes the file name from Content-Disposition, only if it is the shape the backend writes', () => {
        expect(exportFileName('attachment; filename="annual-survey-open-formulieren.zip"')).toBe('annual-survey-open-formulieren.zip');
        for (const bad of [null, undefined, '', 'attachment', 'attachment; filename="../x.zip"', 'attachment; filename="a b.zip"', 'attachment; filename="x.html"', 'attachment; filename="A.zip"']) {
            expect(exportFileName(bad)).toBe(FALLBACK_EXPORT_FILE_NAME);
        }
    });

    it('reads the unmapped count as a whole number only', () => {
        expect(unmappedCount('12')).toBe(12);
        expect(unmappedCount('0')).toBe(0);
        for (const bad of [null, undefined, '', '-1', '1.5', 'x', '1e3', '9999999']) expect(unmappedCount(bad)).toBe(0);
    });

    it('builds the result from the response headers', () => {
        const response = new Response('x', { headers: { 'Content-Disposition': 'attachment; filename="a-open-formulieren.zip"', 'X-Open-Formulieren-Unmapped': '3' } });
        const blob = new Blob(['x']);
        expect(openFormulierenExportOf(blob, response)).toEqual({ blob, fileName: 'a-open-formulieren.zip', unmapped: 3 });
        expect(openFormulierenExportOf(blob)).toEqual({ blob, fileName: FALLBACK_EXPORT_FILE_NAME, unmapped: 0 });
    });

    it('recognises the too-big refusal only', () => {
        expect(exportRefusalIsTooLarge({ status: 422, data: { code: 'form_too_large_for_export' } })).toBe(true);
        for (const other of [{ status: 422, data: { code: 'nothing_to_export' } }, { status: 500 }, undefined, null]) expect(exportRefusalIsTooLarge(other)).toBe(false);
    });
});

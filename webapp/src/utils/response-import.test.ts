import { describe, expect, it } from 'vitest';

import type { ResponseImportTarget } from '@app/store/workspaces/api';

import { cleanMapping, importFileTooLarge, mapsAQuestion, problemPlace, refusalKey, takenTargets } from './response-import';

const targets: ResponseImportTarget[] = [
    { key: 'q:a', label: 'A', kind: 'question', status: 'ok', fieldId: 'a' },
    { key: 'internal:n', label: 'N', kind: 'internal', status: 'ok', fieldId: 'n' },
    { key: 'submitted_at', label: 'S', kind: 'meta', status: 'ok' }
];

describe('response import helpers', () => {
    it('knows the file size limit', () => {
        expect(importFileTooLarge({ size: 5 * 1024 * 1024 })).toBe(false);
        expect(importFileTooLarge({ size: 5 * 1024 * 1024 + 1 })).toBe(true);
    });

    it('takes a target once and drops unmatched columns', () => {
        expect([...takenTargets({ '0': 'q:a', '1': 'q:b', '2': '' }, '1')]).toEqual(['q:a']);
        expect(cleanMapping({ '0': 'q:a', '1': '' })).toEqual({ '0': 'q:a' });
    });

    it('wants a question, not only the time', () => {
        expect(mapsAQuestion({ '0': 'submitted_at' }, targets)).toBe(false);
        expect(mapsAQuestion({ '0': 'submitted_at', '1': 'internal:n' }, targets)).toBe(true);
        expect(mapsAQuestion({}, targets)).toBe(false);
    });

    it('turns the server codes into message keys', () => {
        expect(refusalKey({ status: 415, data: { code: 'unsupported_format' } }).key).toBe('ERROR_unsupported_format');
        expect(refusalKey({ status: 429, data: {} }).key).toBe('ERROR_rate_limited');
        expect(refusalKey({ status: 403, data: {} }).key).toBe('ERROR_forbidden');
        expect(refusalKey({ status: 500 }).key).toBe('ERROR_generic');
        expect(refusalKey({ status: 422, data: { code: 'cell_too_long', row: 9 } }).values?.row).toBe(9);
    });

    it('says where a problem is: the question and the column heading, or the row as a whole', () => {
        const imp = { headers: ['Name', 'Age'], targets };
        expect(problemPlace({ row: 2, column: 1, code: 'x', field: 'a' }, imp)).toEqual({ column: 'Name'.replace('Name', 'Age'), columnNumber: 2, question: 'A' });
        expect(problemPlace({ row: 2, column: null, code: 'x', field: 'a' }, imp)).toEqual({ question: 'A' });
        expect(problemPlace({ row: 2, column: null, code: 'x' }, imp)).toEqual({ question: undefined });
    });
});

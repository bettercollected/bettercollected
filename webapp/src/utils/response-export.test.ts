import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { getAnswerForField } from '@app/utils/form-builder-block-utils';
import { fileNameFromDisposition } from '@app/utils/content-disposition';
import { EXPORT_FORMATS, exportExtension, exportFileName, getItemAnswer, isExportFormat } from '@app/utils/response-export';

const colours: StandardFormFieldDto = {
    id: 'colours',
    index: 2,
    type: FieldTypes.MULTIPLE_CHOICE,
    title: 'Colours',
    properties: {
        allowMultipleSelection: true,
        choices: [
            { id: 'c1', value: 'Red' },
            { id: 'c2', value: 'Green' },
            { id: 'c3', value: 'Blue' }
        ]
    }
};

describe('getAnswerForField separators', () => {
    const answers = { colours: { type: 'choices', choices: { values: ['c1', 'c3'] } } };
    it('keeps the display separator without one', () => {
        expect(getAnswerForField({ answers } as any, colours)).toBe('Red,Blue');
    });
    it('uses the given separator', () => {
        expect(getAnswerForField({ answers } as any, colours, '; ')).toBe('Red; Blue');
    });
    it('keeps ", " for checkboxes and ranking without a separator', () => {
        const checkboxes = {
            id: 'cb',
            type: 'input_checkboxes',
            properties: {
                choices: [
                    { id: 'a', value: 'A' },
                    { id: 'b', value: 'B' }
                ]
            }
        } as unknown as StandardFormFieldDto;
        const response = { answers: { cb: { choices: { values: ['A', 'B'] } } } } as any;
        expect(getAnswerForField(response, checkboxes)).toBe('A, B');
        expect(getAnswerForField(response, checkboxes, '; ')).toBe('A; B');
    });
});

describe('getItemAnswer', () => {
    it('joins a multi-select inside a repeating group item with "; "', () => {
        expect(getItemAnswer({ colours: { type: 'choices', choices: { values: ['c1', 'c2'] } } } as any, colours)).toBe('Red; Green');
        expect(getItemAnswer(undefined, colours)).toBe('');
    });
});

describe('the file the server sent', () => {
    it('is named after the form, safely', () => {
        expect(exportFileName('Survey')).toBe('Survey.csv');
        expect(exportFileName('Survey', 'zip')).toBe('Survey.zip');
        expect(exportFileName('a/b')).toBe('a b.csv');
        expect(exportFileName('x\u0000y')).toBe('x y.csv');
        expect(exportFileName('')).toBe('export.csv');
    });
    it('is a ZIP only when the server says so', () => {
        expect(exportExtension('application/zip')).toBe('zip');
        expect(exportExtension('text/csv; charset=utf-8')).toBe('csv');
        expect(exportExtension(undefined)).toBe('csv');
    });
    it('is a workbook, JSON or a PDF when the server says so', () => {
        expect(exportExtension('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')).toBe('xlsx');
        expect(exportExtension('application/json; charset=utf-8')).toBe('json');
        expect(exportExtension('application/pdf')).toBe('pdf');
        expect(exportFileName('Survey', 'xlsx')).toBe('Survey.xlsx');
        expect(exportFileName('Survey', 'json')).toBe('Survey.json');
    });
    it('offers CSV, Excel and JSON, and nothing else', () => {
        expect(EXPORT_FORMATS).toEqual(['csv', 'xlsx', 'json']);
        expect(['csv', 'xlsx', 'json'].every(isExportFormat)).toBe(true);
        expect([undefined, null, '', 'pdf', 'zip', 'XLSX', 3].some(isExportFormat)).toBe(false);
    });
});

describe('the name a download offers', () => {
    it('is the UTF-8 name when there is one, else the plain one', () => {
        expect(fileNameFromDisposition(`attachment; filename="Etude _2026_.pdf"; filename*=UTF-8''%C3%89tude%20%222026%22.pdf`)).toBe('Étude  2026 .pdf');
        expect(fileNameFromDisposition('attachment; filename="Survey - 1234abcd.pdf"')).toBe('Survey - 1234abcd.pdf');
        expect(fileNameFromDisposition('attachment; filename=plain.pdf')).toBe('plain.pdf');
    });
    it('is made safe to save under, and absent when there is nothing usable', () => {
        expect(fileNameFromDisposition(`attachment; filename*=UTF-8''..%2F..%2Fevil.pdf`)).toBe('.. .. evil.pdf');
        expect(fileNameFromDisposition(`attachment; filename*=UTF-8''%E0%A4%A`)).toBeUndefined();
        expect(fileNameFromDisposition('attachment')).toBeUndefined();
        expect(fileNameFromDisposition(null)).toBeUndefined();
        expect(fileNameFromDisposition(undefined)).toBeUndefined();
    });
});

describe('date range and tags answers on screen and in the sheet', () => {
    const stay: StandardFormFieldDto = { id: 'stay', index: 0, type: FieldTypes.DATE_RANGE, title: 'Stay' };
    const interests: StandardFormFieldDto = { id: 'interests', index: 1, type: FieldTypes.TAGS, title: 'Interests' };

    it('reads a range as one interval and one end alone with its slash (the export itself is built on the server)', () => {
        const range = (start: string, end: string) => ({ answers: { stay: { type: 'date_range', date_range: { start, end } } } }) as any;
        expect(getAnswerForField(range('2026-11-03', '2026-11-07'), stay)).toBe('2026-11-03/2026-11-07');
        expect(getAnswerForField(range('2026-11-03', ''), stay)).toBe('2026-11-03/');
        expect(getAnswerForField(range('', ''), stay)).toBe('');
    });

    it('reads a stored response that spells the slot dateRange', () => {
        expect(getAnswerForField({ answers: { stay: { type: 'date_range', dateRange: { start: '2026-11-03', end: '2026-11-07' } } } } as any, stay)).toBe('2026-11-03/2026-11-07');
    });

    it('shows the tags comma separated on screen (the display separator) and joined with "; " by default', () => {
        const response = { answers: { interests: { type: 'tags', tags: ['a', 'b'] } } } as any;
        expect(getAnswerForField(response, interests, ', ')).toBe('a, b');
        expect(getAnswerForField(response, interests)).toBe('a; b');
        expect(getAnswerForField(response, interests, '; ')).toBe('a; b');
    });
});

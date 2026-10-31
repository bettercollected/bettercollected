import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { getAnswerForField } from '@app/utils/form-builder-block-utils';
import { exportExtension, exportFileName, getItemAnswer } from '@app/utils/response-export';

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
});

describe('date range and tags answers in the export', () => {
    const stay: StandardFormFieldDto = { id: 'stay', index: 0, type: FieldTypes.DATE_RANGE, title: 'Stay' };
    const interests: StandardFormFieldDto = { id: 'interests', index: 1, type: FieldTypes.TAGS, title: 'Interests' };
    const typed = form(undefined, [stay, interests]);
    const answer = (start: string | undefined, end: string | undefined, tags?: string[]) => ({
        stay: { type: 'date_range', date_range: { start, end } },
        ...(tags ? { interests: { type: 'tags', tags } } : {})
    });

    it('writes a range as one cell, YYYY-MM-DD/YYYY-MM-DD, and the tags as one cell joined with "; "', () => {
        const { main } = buildResponsesExport(typed, [response({ responseId: 'r1', answers: answer('2026-11-03', '2026-11-07', ['vegan', 'gluten free']) })]);
        expect(main.headers.slice(0, 3)).toEqual(['Responder ID', 'Stay', 'Interests']);
        expect(main.rows[0].slice(1, 3)).toEqual(['2026-11-03/2026-11-07', 'vegan; gluten free']);
        expect(tableToCsv(main).split('\r\n')[1]).toContain('2026-11-03/2026-11-07,vegan; gluten free');
    });

    it('writes one end alone with its slash, and nothing for no answer', () => {
        const { main } = buildResponsesExport(typed, [
            response({ responseId: 'r1', answers: answer('2026-11-03', '') }),
            response({ responseId: 'r2', answers: answer('', '2026-11-07') }),
            response({ responseId: 'r3', answers: answer('', '') }),
            response({ responseId: 'r4', answers: {} })
        ]);
        expect(main.rows.map((row) => row[1])).toEqual(['2026-11-03/', '/2026-11-07', '', '']);
        expect(main.rows[3][2]).toBe('');
    });

    it('reads a stored response that spells the slot dateRange', () => {
        expect(getAnswerForField({ answers: { stay: { type: 'date_range', dateRange: { start: '2026-11-03', end: '2026-11-07' } } } } as any, stay)).toBe('2026-11-03/2026-11-07');
    });

    it('shows the tags comma separated on screen (the display separator) and joined with "; " by default and in the export', () => {
        const response = { answers: { interests: { type: 'tags', tags: ['a', 'b'] } } } as any;
        expect(getAnswerForField(response, interests, ', ')).toBe('a, b');
        expect(getAnswerForField(response, interests)).toBe('a; b');
        expect(getAnswerForField(response, interests, '; ')).toBe('a; b');
    });

    // The guard is on the CSV (tableToCsv): the table keeps the answer as written.
    const csvCell = (tags: string[]) => {
        const { main } = buildResponsesExport(typed, [response({ responseId: 'r1', answers: answer(undefined, undefined, tags) })]);
        return tableToCsv(main).split('\r\n')[1].split(',')[main.headers.indexOf('Interests')];
    };

    it.each([
        ['=SUM(1+1)', "'=SUM(1+1)"],
        ['+31 6 1234', "'+31 6 1234"],
        ['-x', "'-x"],
        ['@home', "'@home"],
        ['=1+1', "'=1+1"]
    ])('neutralises a tags cell that starts with the tag %j, so a spreadsheet reads text', (tag, cell) => {
        expect(csvCell([tag, 'b'])).toBe(`${cell}; b`);
        expect(csvCell([tag])).toBe(cell);
    });

    it('leaves a formula character after the first tag alone: the cell does not start with it', () => {
        expect(csvCell(['ok', '=1+1', '+2', '-3', '@4'])).toBe('ok; =1+1; +2; -3; @4');
    });

    it('keeps a plain negative number as it is, as for any text answer', () => {
        expect(csvCell(['-5'])).toBe('-5');
    });
});

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

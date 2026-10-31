import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { getAnswerDisplayText } from '@app/utils/form-builder-block-utils';
import { formFormatLanguage } from '@app/utils/response-page';

const day: StandardFormFieldDto = { id: 'born', index: 0, type: FieldTypes.DAY, title: 'Born' };
const stay: StandardFormFieldDto = { id: 'stay', index: 1, type: FieldTypes.DATE_RANGE, title: 'Stay' };
const response = { answers: { born: { type: 'date', date: '1990-11-05' }, stay: { type: 'date_range', date_range: { start: '2026-11-03', end: '2026-11-07' } } } } as any;

describe('what the responses table and the detail page show for days', () => {
    it('writes a day and a range in the app\'s date style, in English by default', () => {
        expect(getAnswerDisplayText(response, day)).toBe('5 November 1990');
        expect(getAnswerDisplayText(response, stay)).toBe('3 November 2026 – 7 November 2026');
    });

    it('writes them in Dutch for a Dutch form (its language as the form declares it)', () => {
        const language = formFormatLanguage('nl-NL');
        expect(getAnswerDisplayText(response, day, language)).toBe('5 november 1990');
        expect(getAnswerDisplayText(response, stay, language)).toBe('3 november 2026 – 7 november 2026');
        expect(formFormatLanguage('nl')).toBe('nl');
        expect(formFormatLanguage(undefined)).toBe('en');
        expect(formFormatLanguage('de')).toBe('en');
    });
});

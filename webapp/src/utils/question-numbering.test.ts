import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import { formNumberingState, hasSeveralPages, plainQuestionNumbers } from './question-numbering';

const page = (id: string, show?: boolean): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SLIDE, properties: { fields: [], ...(show === undefined ? {} : { showQuestionNumbers: show }) } });
const q = (id: string, type: FieldTypes = FieldTypes.SHORT_TEXT): StandardFormFieldDto => ({ id, index: 0, type });

describe('question numbering', () => {
    it('is on, off or mixed across the question pages', () => {
        expect(formNumberingState([page('a'), page('b')])).toBe('off');
        expect(formNumberingState([page('a', true), page('b', true)])).toBe('on');
        expect(formNumberingState([page('a', true), page('b', false)])).toBe('mixed');
        expect(formNumberingState([])).toBe('off');
    });

    it('numbers questions, not content, by page on a multi-page form', () => {
        const fields = [q('a'), q('t', FieldTypes.TEXT), q('b', FieldTypes.MULTIPLE_CHOICE)];
        expect(plainQuestionNumbers(fields, 2, true)).toEqual({ a: '2.1', b: '2.2' });
        expect(plainQuestionNumbers(fields, 1, false)).toEqual({ a: '1.', b: '2.' });
        expect(hasSeveralPages([page('a')])).toBe(false);
        expect(hasSeveralPages([page('a'), page('b')])).toBe(true);
    });
});

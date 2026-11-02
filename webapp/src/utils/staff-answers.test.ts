import { describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';

import { changedAnswers, editableQuestions, inputsFor, lockedQuestions, pageQuestions, staffAnswer } from './staff-answers';

const q = (id: string, type: string, extra: Record<string, any> = {}): any => ({ id, type, title: id, ...extra });
const FORM: any = {
    fields: [
        {
            id: 'p1',
            type: FieldTypes.SLIDE,
            properties: {
                fields: [
                    q('name', FieldTypes.SHORT_TEXT),
                    q('age', FieldTypes.NUMBER),
                    q('colour', FieldTypes.DROP_DOWN, {
                        properties: {
                            choices: [
                                { id: 'red', value: 'Red' },
                                { id: 'blue', value: 'Blue' }
                            ]
                        }
                    }),
                    q('sig', FieldTypes.SIGNATURE),
                    q('doc', FieldTypes.FILE_UPLOAD),
                    q('home', FieldTypes.ADDRESS),
                    q('ref', FieldTypes.SHORT_TEXT, { internal: true }),
                    q('total', FieldTypes.CALCULATED),
                    q('intro', FieldTypes.STATEMENT)
                ]
            }
        }
    ]
};

describe('which questions staff can change', () => {
    it('lists the types the editor knows, never an internal field', () => {
        expect(editableQuestions(FORM).map((f) => f.id)).toEqual(['name', 'age', 'colour']);
    });

    it('lists what cannot be changed here, leaving out what is not a question', () => {
        expect(lockedQuestions(FORM).map((f) => f.id)).toEqual(['sig', 'doc', 'home']);
    });

    it('reads the questions of every page in order', () => {
        const two: any = { fields: [FORM.fields[0], { id: 'p2', type: FieldTypes.SLIDE, properties: { fields: [q('x', FieldTypes.EMAIL)] } }] };
        expect(pageQuestions(two).at(-1)?.id).toBe('x');
        expect(pageQuestions(undefined)).toEqual([]);
    });
});

describe('what is sent', () => {
    const fields = editableQuestions(FORM);
    const stored: any = {
        name: { type: 'text', text: 'Ada' },
        age: { type: 'number', number: 36 },
        colour: { type: 'choice', choice: { value: 'red' } }
    };

    it('starts from the stored answers', () => {
        expect(inputsFor(fields, stored)).toEqual({ name: 'Ada', age: '36', colour: 'red' });
    });

    it('sends nothing when nothing changed', () => {
        expect(changedAnswers(fields, stored, inputsFor(fields, stored))).toEqual({});
    });

    it('sends only the questions that changed, as respondent answers', () => {
        const values = { ...inputsFor(fields, stored), name: 'Ada L', colour: 'blue' };
        expect(changedAnswers(fields, stored, values)).toEqual({
            name: { field: { id: 'name' }, type: 'text', text: 'Ada L' },
            colour: { field: { id: 'colour' }, type: 'choice', choice: { value: 'blue' } }
        });
    });

    it('clears a text answer with an empty text, and leaves other types as they are when blanked', () => {
        const values = { ...inputsFor(fields, stored), name: '', age: '' };
        expect(changedAnswers(fields, stored, values)).toEqual({ name: { field: { id: 'name' }, type: 'text', text: '' } });
        expect(staffAnswer(fields[1], '')).toBeUndefined();
    });

    it('gives an answer to a question that had none', () => {
        expect(changedAnswers(fields, {}, { name: 'Bo', age: '', colour: '' })).toEqual({ name: { field: { id: 'name' }, type: 'text', text: 'Bo' } });
    });
});

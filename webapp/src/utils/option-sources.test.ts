import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { choiceAnswerText } from '@app/utils/conditional-logic';
import { getAnswerForField } from '@app/utils/form-builder-block-utils';
import { answerLabels, answerSourceQuestions, chosenOptionIds, formSharesAnswers, parentCandidates, parentKey, parentLabelsOf, parentOptionIds, shareNoticeTokenToSend, shareableQuestions, sourcedAnswerTexts } from '@app/utils/option-sources';
import { choiceRows } from '@app/utils/response-page';
import { serverAnswerErrors } from '@app/utils/server-answer-errors';

const sourced = (id: string, extra: Partial<StandardFormFieldDto['properties']> = {}, type = FieldTypes.DROP_DOWN): StandardFormFieldDto =>
    ({ id, index: 0, type, properties: { optionSource: { kind: 'list', listId: 'l1' }, ...extra } }) as StandardFormFieldDto;

describe('what a choice answer holds', () => {
    it('reads the chosen ids of a single and of a multiple choice', () => {
        expect(chosenOptionIds({ choice: { value: 'li1' } })).toEqual(['li1']);
        expect(chosenOptionIds({ choices: { values: ['a', 'b', ''] } })).toEqual(['a', 'b']);
        expect(chosenOptionIds({ choice: { other: 'Else' } })).toEqual([]);
        expect(chosenOptionIds(undefined)).toEqual([]);
    });

    it('reads the label snapshot, and builds the texts in the order chosen with an "Other" text last', () => {
        const one = { choice: { value: 'li1', label: 'Amsterdam' } };
        expect(answerLabels(one)).toEqual({ li1: 'Amsterdam' });
        const many = { choices: { values: ['b', 'a'], labels: { a: 'Alice', b: 'Bob' }, other: ' Dave ' } };
        expect(sourcedAnswerTexts(many)).toEqual(['Bob', 'Alice', 'Dave']);
        // an id without a stored text is never shown as an id
        expect(sourcedAnswerTexts({ choice: { value: 'li1' } })).toEqual([]);
    });
});

describe('the places an answer to a sourced question is shown', () => {
    const field = sourced('who');
    const many = sourced('whom', { allowMultipleSelection: true }, FieldTypes.MULTIPLE_CHOICE);
    const answers = { who: { choice: { value: 'li1', label: 'Alice Example' } }, whom: { choices: { values: ['fa1', 'fa2'], labels: { fa1: 'Bob', fa2: 'Carol' } } } };

    it('writes the label in exports, in piping and on the response page, never the id', () => {
        expect(getAnswerForField({ answers } as any, field)).toBe('Alice Example');
        expect(getAnswerForField({ answers } as any, many, '; ')).toBe('Bob; Carol');
        expect(choiceAnswerText(answers.who, field)).toBe('Alice Example');
        expect(choiceAnswerText(answers.whom, many)).toEqual(['Bob', 'Carol']);
        expect(choiceRows(field, answers.who, false)).toEqual([{ key: 'li1', label: 'Alice Example', selected: true }]);
        expect(choiceRows(many, answers.whom, true).map((row) => row.label)).toEqual(['Bob', 'Carol']);
    });

    it('keeps reading a question that has its own options as before', () => {
        const own = { id: 'plain', index: 0, type: FieldTypes.DROP_DOWN, properties: { choices: [{ id: 'c1', value: 'Red' }] } } as StandardFormFieldDto;
        expect(getAnswerForField({ answers: { plain: { choice: { value: 'c1', label: 'Forged' } } } } as any, own)).toBe('Red');
    });
});

describe('a dependent list', () => {
    const country = {
        id: 'country',
        index: 0,
        type: FieldTypes.DROP_DOWN,
        properties: {
            choices: [
                { id: 'nl', value: 'Netherlands' },
                { id: 'de', value: 'Germany' }
            ]
        }
    } as StandardFormFieldDto;
    const city = sourced('city', { optionSource: { kind: 'list', listId: 'l1', parentFieldId: 'country' } });
    const slides = [{ id: 's', index: 0, type: FieldTypes.SLIDE, properties: { fields: [country, city, { id: 'later', index: 2, type: FieldTypes.DROP_DOWN } as StandardFormFieldDto] } } as StandardFormFieldDto];

    it('follows the ids chosen in its parent, and names them by their text', () => {
        const answers = { country: { choice: { value: 'nl' } } };
        expect(parentOptionIds(city, answers)).toEqual(['nl']);
        expect(parentLabelsOf(city, answers, slides)).toEqual(['Netherlands']);
        expect(parentOptionIds(city, {})).toEqual([]);
        expect(parentOptionIds(country, answers)).toEqual([]);
        expect(parentKey(['b', 'a'])).toBe(parentKey(['a', 'b']));
    });

    it('offers only the earlier choice questions as a parent, and the usable questions of another form', () => {
        expect(parentCandidates(slides, 'city').map((q) => q.id)).toEqual(['country']);
        const form = {
            fields: [
                {
                    id: 's',
                    type: FieldTypes.SLIDE,
                    properties: {
                        fields: [
                            { id: 'name', type: FieldTypes.SHORT_TEXT, properties: { shareAsChoices: true } },
                            { id: 'nickname', type: FieldTypes.SHORT_TEXT },
                            { id: 'mail', type: FieldTypes.EMAIL, properties: { shareAsChoices: true } },
                            { id: 'staff', type: FieldTypes.SHORT_TEXT, internal: true, properties: { shareAsChoices: true } },
                            { id: 'role', type: FieldTypes.DROP_DOWN, properties: { shareAsChoices: true } },
                            sourced('sourced', { shareAsChoices: true })
                        ]
                    }
                }
            ]
        };
        // only the questions that opted in (and can: never an email, an internal question or one with a source)
        expect(answerSourceQuestions(form as any).map((q) => q.id)).toEqual(['name', 'role']);
        // what a creator could turn sharing on for
        expect(shareableQuestions(form as any).map((q) => q.id)).toEqual(['name', 'nickname', 'role']);
        expect(formSharesAnswers(form.fields as any)).toBe(true);
        expect(formSharesAnswers([{ id: 's', type: FieldTypes.SLIDE, properties: { fields: [{ id: 'm', type: FieldTypes.EMAIL, properties: { shareAsChoices: true } }] } }] as any)).toBe(false);
    });
});

describe('the server refusing an option', () => {
    it('is a problem on the question, in the words of the options rule', () => {
        const error = { status: 422, data: { code: 'invalid_answers', errors: [{ fieldId: 'city', rule: 'option_unavailable' }] } };
        expect(serverAnswerErrors(error)).toEqual([{ fieldId: 'city', rule: 'option_unavailable' }]);
    });
});

describe('the share notice token a submission carries', () => {
    const page = (shares: boolean | undefined): StandardFormFieldDto[] => [{ id: 's', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name', properties: { shareAsChoices: shares } }] } } as StandardFormFieldDto];

    it('goes back only from a page that shows the notice', () => {
        expect(shareNoticeTokenToSend({ fields: page(true), shareNoticeToken: 'tok' })).toBe('tok');
        expect(shareNoticeTokenToSend({ fields: page(undefined), shareNoticeToken: 'tok' })).toBeNull();
        expect(shareNoticeTokenToSend({ fields: page(false), shareNoticeToken: 'tok' })).toBeNull();
    });

    it('is never made up: no token, an empty one or no form sends nothing', () => {
        expect(shareNoticeTokenToSend({ fields: page(true) })).toBeNull();
        expect(shareNoticeTokenToSend({ fields: page(true), shareNoticeToken: '' })).toBeNull();
        expect(shareNoticeTokenToSend(undefined)).toBeNull();
    });
});

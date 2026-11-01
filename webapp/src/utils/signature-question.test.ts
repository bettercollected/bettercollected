import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison } from '@app/models/types/form-builder-shared';
import { checkAnswerRules } from '@app/utils/answer-rules';
import { evaluateConditions, getComparableAnswerValue } from '@app/utils/conditional-logic';
import { getAnswerDisplayText, getAnswerForField } from '@app/utils/form-builder-block-utils';
import { answersForDraft, hasSignatureQuestion } from '@app/utils/form-drafts';
import { answerLines } from '@app/utils/review-page';
import { serverAnswerErrors, serverInvalidations } from '@app/utils/server-answer-errors';
import { comparisonsForField, isConditionSource, newConditionFor } from '@app/views/molecules/form-builder/condition-editor-shared';
import { sendsDrawnSignature } from '@app/views/organism/form/use-finish-form';

const sign: StandardFormFieldDto = { id: 'sig', index: 0, type: FieldTypes.SIGNATURE, title: 'Sign' };
const slides: StandardFormFieldDto[] = [{ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' }, sign] } } as StandardFormFieldDto];
const typed = { type: 'signature', signature: { method: 'typed', name: 'Ada Lovelace' } };
const drawn = { type: 'signature', signature: { method: 'drawn', file_id: 'img-1' } };
const t = (key: string) => key;

describe('conditions on a signature', () => {
    const condition = (comparison: Comparison, value?: string) => [{ fieldId: 'sig', fieldType: FieldTypes.SIGNATURE, comparison, value }];

    it('ask only whether it is signed, whichever way it was', () => {
        for (const answer of [typed, drawn]) {
            expect(evaluateConditions(undefined, condition(Comparison.IS_NOT_EMPTY), { sig: answer })).toBe(true);
            expect(evaluateConditions(undefined, condition(Comparison.IS_EMPTY), { sig: answer })).toBe(false);
        }
        expect(evaluateConditions(undefined, condition(Comparison.IS_EMPTY), {})).toBe(true);
        expect(evaluateConditions(undefined, condition(Comparison.IS_NOT_EMPTY), {})).toBe(false);
    });

    it('never hold for any other comparison, and never expose the name', () => {
        for (const comparison of [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.CONTAINS, Comparison.STARTS_WITH, Comparison.GREATER_THAN]) {
            expect(evaluateConditions(undefined, condition(comparison, 'Ada Lovelace'), { sig: typed })).toBe(false);
            expect(evaluateConditions(undefined, condition(comparison, 'signed'), { sig: typed })).toBe(false);
        }
        expect(getComparableAnswerValue(typed, FieldTypes.SIGNATURE)).toBe('signed');
        expect(getComparableAnswerValue({ type: 'signature' }, FieldTypes.SIGNATURE)).toBeUndefined();
    });

    it('are offered in the builder as signed or not, from the first position', () => {
        expect(comparisonsForField(sign)).toEqual([Comparison.IS_NOT_EMPTY, Comparison.IS_EMPTY]);
        expect(isConditionSource(sign)).toBe(true);
        expect(newConditionFor([{ field: sign } as any]).comparison).toBe(Comparison.IS_NOT_EMPTY);
    });
});

describe('what the page checks', () => {
    it('flags a typed name that is not well formed, and a drawn one with no image', () => {
        expect(checkAnswerRules(sign, typed)).toEqual([]);
        expect(checkAnswerRules(sign, drawn)).toEqual([]);
        expect(checkAnswerRules(sign, { type: 'signature', signature: { method: 'typed', name: 'a​b' } })).toEqual(['FORMAT']);
        expect(checkAnswerRules(sign, { type: 'signature', signature: { method: 'typed', name: 'x'.repeat(101) } })).toEqual(['TOO_LONG']);
        expect(checkAnswerRules(sign, { type: 'signature', signature: { method: 'drawn' } })).toEqual(['SIGNATURE_IMAGE']);
        // an empty answer is Required's to say; another shape is the server's "type"
        expect(checkAnswerRules(sign, undefined)).toEqual([]);
        expect(checkAnswerRules(sign, { type: 'signature' })).toEqual([]);
        expect(checkAnswerRules(sign, { type: 'signature', signature: 'Ada' })).toEqual([]);
    });
});

describe('what the server says', () => {
    it('puts a refused image on its question', () => {
        const errors = serverAnswerErrors({ status: 422, data: { code: 'invalid_answers', errors: [{ fieldId: 'sig', rule: 'signature_image' }] } });
        expect(serverInvalidations(slides, errors!)).toEqual({ sig: ['SIGNATURE_IMAGE'] });
    });
});

describe('where it shows', () => {
    const response = (answer: any) => ({ answers: { sig: answer } }) as any;

    it('is the typed name or a marker in exports and tables, never an image or a link', () => {
        expect(getAnswerForField(response(typed), sign)).toBe('Ada Lovelace');
        expect(getAnswerForField(response({ ...drawn, signature: { ...drawn.signature, url: 'https://files.example/x?signed' } }), sign)).toBe('[drawn signature]');
        expect(getAnswerDisplayText(response(drawn), sign)).toBe('[drawn signature]');
        expect(getAnswerForField(response(undefined), sign)).toBe('');
    });

    it('reads the drawn marker in the screen\'s language in the table, and keeps the server\'s marker for the CSV', () => {
        expect(getAnswerDisplayText(response(drawn), sign, 'nl', '[getekende handtekening]')).toBe('[getekende handtekening]');
        expect(getAnswerDisplayText(response(typed), sign, 'nl', '[getekende handtekening]')).toBe('Ada Lovelace');
        expect(getAnswerDisplayText(response(undefined), sign, 'nl', '[getekende handtekening]')).toBe('');
        // the export path takes no translation
        expect(getAnswerForField(response(drawn), sign)).toBe('[drawn signature]');
    });

    it('is the name, or that it is drawn, on the review page', () => {
        expect(answerLines(sign, { sig: typed }, 'en', t)).toEqual(['Ada Lovelace']);
        expect(answerLines(sign, { sig: drawn }, 'en', t)).toEqual(['SIGNATURE.REVIEW_DRAWN']);
        expect(answerLines(sign, {}, 'en', t)).toEqual([]);
    });
});

describe('saved drafts', () => {
    it('keep a typed signature and leave out a drawn one (files are not kept)', () => {
        expect(hasSignatureQuestion(slides)).toBe(true);
        expect(hasSignatureQuestion([{ id: 'p', index: 0, type: FieldTypes.SLIDE, properties: { fields: [slides[0].properties!.fields![0]] } } as StandardFormFieldDto])).toBe(false);
        expect(answersForDraft(slides, { sig: typed, name: { type: 'text', text: 'Ada' } })).toEqual({ sig: typed, name: { type: 'text', text: 'Ada' } });
        expect(answersForDraft(slides, { sig: drawn, name: { type: 'text', text: 'Ada' } })).toEqual({ name: { type: 'text', text: 'Ada' } });
    });
});

describe('a submission that carries a drawing', () => {
    it('is told by a file part for a signature question', () => {
        expect(sendsDrawnSignature(slides, [{ fieldId: 'sig' }])).toBe(true);
        expect(sendsDrawnSignature(slides, [{ fieldId: 'name' }])).toBe(false);
        expect(sendsDrawnSignature(slides, [])).toBe(false);
        expect(sendsDrawnSignature(undefined, [{ fieldId: 'sig' }])).toBe(false);
    });
});

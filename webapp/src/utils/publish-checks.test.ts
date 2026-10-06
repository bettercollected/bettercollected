import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import { asksForIdentity, getPublishProblems, problemsFromPublishError } from './publish-checks';

const q = (id: string, type: string, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type, title: 'Question', ...extra }) as StandardFormFieldDto;
const page = (...fields: StandardFormFieldDto[]) => [{ id: 'page', index: 0, type: FieldTypes.SLIDE, properties: { fields } } as StandardFormFieldDto];
const codes = (...fields: StandardFormFieldDto[]) => getPublishProblems(page(...fields)).map((p) => [p.code, p.fieldId]);

describe('publish checks: why we ask this', () => {
    it('needs a reason on email and phone questions', () => {
        expect(codes(q('e', FieldTypes.EMAIL))).toEqual([['missing_why_we_ask', 'e']]);
        expect(codes(q('p', FieldTypes.PHONE_NUMBER, { properties: { whyWeAsk: '  ' } }))).toEqual([['missing_why_we_ask', 'p']]);
        expect(codes(q('e', FieldTypes.EMAIL, { properties: { whyWeAsk: 'To send your receipt.' } }))).toEqual([]);
    });

    it('recognises ID-number questions narrowly', () => {
        for (const title of ['Uw BSN', 'Burgerservicenummer', 'Passport number', 'ID-nummer', 'Social security number']) {
            expect(asksForIdentity(q('t', FieldTypes.SHORT_TEXT, { title }))).toBe(true);
        }
        for (const title of ['Order ID', 'Passport photo attached?', 'Your idea', 'Bsnl']) {
            expect(asksForIdentity(q('t', FieldTypes.SHORT_TEXT, { title }))).toBe(false);
        }
        const rich = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Your passport no.' }] }] };
        expect(asksForIdentity(q('t', FieldTypes.NUMBER, { title: rich as any }))).toBe(true);
    });

    it('skips internal fields and checks repeating-group questions', () => {
        expect(codes(q('e', FieldTypes.EMAIL, { internal: true }))).toEqual([]);
        const group = q('g', FieldTypes.GROUP, { properties: { repeat: { maxItems: 3 } as any, fields: [q('child', FieldTypes.EMAIL)] } });
        expect(codes(group)).toEqual([['missing_why_we_ask', 'child']]);
    });
});

describe('publish checks: no required dead ends', () => {
    it('flags required content with nothing to answer', () => {
        expect(codes(q('i', FieldTypes.IMAGE_CONTENT, { validations: { required: true } }))).toEqual([['required_unanswerable', 'i']]);
        expect(codes(q('s', FieldTypes.TEXT, { validations: { required: true } }))).toEqual([['required_unanswerable', 's']]);
        expect(codes(q('g', FieldTypes.GROUP, { validations: { required: true } }))).toEqual([['required_unanswerable', 'g']]);
    });

    it('flags a required choice without options, not one with options or a yes/no', () => {
        expect(codes(q('d', FieldTypes.DROP_DOWN, { validations: { required: true }, properties: { choices: [{ id: 'c', value: '' }] } }))).toEqual([['required_unanswerable', 'd']]);
        expect(codes(q('d', FieldTypes.DROP_DOWN, { validations: { required: true }, properties: { choices: [{ id: 'c', value: 'A' }] } }))).toEqual([]);
        expect(codes(q('y', FieldTypes.YES_NO, { validations: { required: true } }))).toEqual([]);
    });

    it('does not flag required questions hidden by logic: respondents are only asked what they see', () => {
        const hidden = q('h', FieldTypes.SHORT_TEXT, { validations: { required: true }, properties: { logic: { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'x', comparison: 'is_equal', value: 'y' }] } as any } });
        expect(codes(hidden)).toEqual([]);
    });
});

describe('publish checks: no pre-ticked answers', () => {
    it('blocks a yes/no or choice whose value picks one of its options', () => {
        expect(codes(q('c', FieldTypes.YES_NO, { value: 'Yes' }))).toEqual([['preset_answer', 'c']]);
        expect(
            codes(
                q('m', FieldTypes.MULTIPLE_CHOICE, {
                    value: 'subscribe',
                    properties: {
                        choices: [
                            { id: '1', value: 'Subscribe' },
                            { id: '2', value: 'No' }
                        ]
                    }
                })
            )
        ).toEqual([['preset_answer', 'm']]);
    });

    it('ignores a legacy title kept in value', () => {
        expect(codes(q('c', FieldTypes.YES_NO, { title: undefined, value: 'Do you agree to be contacted?' }))).toEqual([]);
    });
});

describe('problemsFromPublishError', () => {
    it("reads the server's refusal", () => {
        const error = { status: 422, data: { code: 'form_not_publishable', message: 'x', problems: [{ code: 'missing_why_we_ask', fieldId: 'e', message: 'Add a reason' }] } };
        expect(problemsFromPublishError(error)).toEqual([{ code: 'missing_why_we_ask', fieldId: 'e', message: 'Add a reason' }]);
        expect(problemsFromPublishError({ status: 500, data: 'oops' })).toEqual([]);
    });
});

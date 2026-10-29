import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/form-builder';
import { FormValidationError } from '@app/models/enums/form-validation';

import { FORMAT_PRESETS } from './answer-rules';
import { validateFormFieldAnswer, validateFormOpen, validateSlide } from './vvalidation-utils';

const q = (id: string, required = false, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, ...(required ? { validations: { required: true } } : {}), ...extra });

const slide = (fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id: 's', index: 0, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;

describe('validateSlide — the responder Next-button gate', () => {
    it('flags required fields with no answer', () => {
        const invalid = validateSlide(slide([q('a', true), q('b')]), {});
        expect(Object.keys(invalid)).toEqual(['a']);
    });

    it('passes required fields that have an answer', () => {
        const invalid = validateSlide(slide([q('a', true)]), { a: { type: 'text', text: 'hi' } });
        expect(Object.keys(invalid)).toEqual([]);
    });

    it('optional unanswered fields never block', () => {
        const invalid = validateSlide(slide([q('a'), q('b')]), {});
        expect(Object.keys(invalid)).toEqual([]);
    });

    it('required matrix fields check every row', () => {
        const matrix = q('m', true, {
            type: FieldTypes.MATRIX,
            properties: { fields: [q('row1'), q('row2')] }
        });
        // one row unanswered → the matrix is flagged
        const invalid = validateSlide(slide([matrix]), { row1: { type: 'choice', choice: { value: 'x' } } });
        expect(Object.keys(invalid)).toEqual(['m']);
        // all rows answered → passes
        const ok = validateSlide(slide([matrix]), { row1: { type: 'choice', choice: { value: 'x' } }, row2: { type: 'choice', choice: { value: 'y' } } });
        expect(Object.keys(ok)).toEqual([]);
    });
});

describe('validateFormOpen', () => {
    it('forms with no close date are open', () => {
        expect(validateFormOpen(undefined)).toBe(true);
    });

    it('future close dates are open, past ones are closed', () => {
        expect(validateFormOpen('2999-01-01T00:00:00Z')).toBe(true);
        expect(validateFormOpen('2000-01-01T00:00:00Z')).toBe(false);
    });
});

describe('validateFormFieldAnswer — legacy (v1) answer checks', () => {
    const legacy = (type: FormBuilderTagNames, validations: Record<string, unknown>) => ({ id: 'f', index: 0, type, validations }) as unknown as StandardFormFieldDto;

    it('flags a text that does NOT match a built-in format (it used to flag matching ones)', () => {
        const field = legacy(FormBuilderTagNames.INPUT_SHORT_TEXT, { regex: FORMAT_PRESETS.find((preset) => preset.id === 'postcode_nl')!.pattern });
        expect(validateFormFieldAnswer(field, { text: '1234 AB' } as any)).toEqual([]);
        expect(validateFormFieldAnswer(field, { text: 'abcd' } as any)).toEqual([FormValidationError.REGEX_PATTERN]);
    });

    it('leaves a pattern a creator wrote to the server', () => {
        const field = legacy(FormBuilderTagNames.INPUT_SHORT_TEXT, { regex: '^[0-9]{4}$' });
        expect(validateFormFieldAnswer(field, { text: 'abcd' } as any)).toEqual([]);
    });

    it('a limit of 0 is a limit, and too many choices is its own error', () => {
        const number = legacy(FormBuilderTagNames.INPUT_NUMBER, { minValue: 0 });
        expect(validateFormFieldAnswer(number, { number: -1 } as any)).toEqual([FormValidationError.INSUFFICIENT_VALUE]);
        const choices = legacy(FormBuilderTagNames.INPUT_CHECKBOXES, { maxChoices: 1 });
        expect(validateFormFieldAnswer(choices, { choices: { values: ['a', 'b'] } } as any)).toEqual([FormValidationError.EXCEEDS_MAX_CHOICES]);
    });
});

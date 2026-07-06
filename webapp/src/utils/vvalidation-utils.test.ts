import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { validateFormOpen, validateSlide } from './vvalidation-utils';

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

import { describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';

import { clampSpan, columnPlacementClass, fieldSpacingClass, greetingAlignClass, greetingTextAlignment, layoutOfPage } from './form-column';

describe('greetingTextAlignment (welcome and ending pages)', () => {
    it('centres the content when the page is set to "Centered"', () => {
        expect(greetingTextAlignment(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND)).toBe('center');
        expect(greetingAlignClass(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND)).toContain('text-center');
        expect(greetingAlignClass(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND)).toContain('items-center');
    });

    it('keeps a left edge for "Left aligned"', () => {
        expect(greetingTextAlignment(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN)).toBe('start');
        expect(greetingAlignClass(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN)).toContain('items-start');
    });

    it('keeps a left edge for the image layouts and an unset layout', () => {
        for (const layout of [FormSlideLayout.TWO_COLUMN_IMAGE_LEFT, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND, undefined, null]) {
            expect(greetingTextAlignment(layout)).toBe('start');
        }
    });
});

describe('columnPlacementClass', () => {
    it('puts the column against the left gutter only for "Left aligned" pages', () => {
        expect(columnPlacementClass(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN)).toBe('mr-auto');
        expect(columnPlacementClass(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND)).toBe('mx-auto');
        expect(columnPlacementClass(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toBe('mx-auto');
        expect(columnPlacementClass(undefined)).toBe('mx-auto');
    });
});

describe('clampSpan', () => {
    it('defaults to the full row and stays within 1–12', () => {
        expect(clampSpan({ properties: {} as any })).toBe(12);
        expect(clampSpan({ properties: { colSpan: 6 } as any })).toBe(6);
        expect(clampSpan({ properties: { colSpan: 0 } as any })).toBe(1);
        expect(clampSpan({ properties: { colSpan: 40 } as any })).toBe(12);
        expect(clampSpan(undefined)).toBe(12);
    });
});

describe('fieldSpacingClass', () => {
    it('pulls the next question closer to a text block, but not the button after a last text block', () => {
        expect(fieldSpacingClass({ type: FieldTypes.TEXT }, false)).toBe('-mb-6');
        expect(fieldSpacingClass({ type: FieldTypes.TEXT }, true)).toBe('');
        expect(fieldSpacingClass({ type: FieldTypes.SHORT_TEXT }, false)).toBe('');
    });
});

describe('layoutOfPage', () => {
    const form = {
        welcomePage: { layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND },
        thankyouPage: [{ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN }],
        fields: [{ id: 'p1', type: FieldTypes.SLIDE, properties: { layout: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT } }]
    } as any;

    it('reads the welcome page, the ending page and question pages', () => {
        expect(layoutOfPage(form, -1)).toBe(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
        expect(layoutOfPage(form, -2)).toBe(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN);
        expect(layoutOfPage(form, 0)).toBe(FormSlideLayout.TWO_COLUMN_IMAGE_LEFT);
    });

    it('survives forms without an ending page or the page asked for', () => {
        expect(layoutOfPage({ thankyouPage: null } as any, -2)).toBeUndefined();
        expect(layoutOfPage(form, 5)).toBeUndefined();
        expect(layoutOfPage(undefined, -1)).toBeUndefined();
    });
});

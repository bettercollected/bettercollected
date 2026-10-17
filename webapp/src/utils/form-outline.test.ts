import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, LogicalOperator } from '@app/models/types/form-builder-shared';

import { outlinePageName, pageKey, pageStatus, questionDropTarget, questionKey, questionMatches, resolveOutlineDrop } from './form-outline';

const flat = [pageKey('p1'), questionKey('a'), questionKey('b'), pageKey('p2'), questionKey('c'), pageKey('p3')];

describe('resolveOutlineDrop', () => {
    it('reads a page move from the new order of the page keys', () => {
        expect(resolveOutlineDrop([pageKey('p1'), pageKey('p2'), pageKey('p3')], pageKey('p3'), pageKey('p1'))).toEqual({ kind: 'page', from: 2, to: 0 });
    });

    it('moving a question down past a page header puts it at the top of that page', () => {
        expect(resolveOutlineDrop(flat, questionKey('b'), pageKey('p2'))).toEqual({ kind: 'question', fieldId: 'b', toPageId: 'p2', afterFieldId: null });
    });

    it('moving a question up past a page header puts it at the end of the page above', () => {
        expect(resolveOutlineDrop(flat, questionKey('c'), pageKey('p2'))).toEqual({ kind: 'question', fieldId: 'c', toPageId: 'p1', afterFieldId: 'b' });
    });

    it('onto an empty page', () => {
        expect(resolveOutlineDrop(flat, questionKey('a'), pageKey('p3'))).toEqual({ kind: 'question', fieldId: 'a', toPageId: 'p3', afterFieldId: null });
    });

    it('within a page', () => {
        expect(resolveOutlineDrop(flat, questionKey('a'), questionKey('b'))).toEqual({ kind: 'question', fieldId: 'a', toPageId: 'p1', afterFieldId: 'b' });
    });

    it('above the first page header: the top of the first page', () => {
        expect(resolveOutlineDrop(flat, questionKey('a'), pageKey('p1'))).toEqual({ kind: 'question', fieldId: 'a', toPageId: 'p1', afterFieldId: null });
    });

    it('nothing to do when dropped on itself', () => {
        expect(resolveOutlineDrop(flat, questionKey('a'), questionKey('a'))).toBeNull();
    });
});

describe('questionDropTarget', () => {
    const slides = [{ id: 'p1', properties: { fields: [{ id: 'a' }, { id: 'hidden' }, { id: 'b' }] } }] as StandardFormFieldDto[];
    it('counts positions without the moving question, after the anchor', () => {
        expect(questionDropTarget(slides, 'a', 'p1', 'b')).toEqual({ toPageIndex: 0, toIndex: 2 });
        expect(questionDropTarget(slides, 'b', 'p1', null)).toEqual({ toPageIndex: 0, toIndex: 0 });
    });
});

describe('pageStatus', () => {
    const slide = (fields: any[], jumps?: any[]) => ({ id: 'p', type: FieldTypes.SLIDE, properties: { fields, jumps } }) as StandardFormFieldDto;

    it('flags an empty page', () => {
        expect(pageStatus(slide([]), new Set(['p']))).toMatchObject({ empty: true, hasLogic: false, brokenJumps: 0, missingWhyWeAsk: 0, internal: 0 });
    });

    it('counts broken jumps, internal questions and identity questions without a reason', () => {
        const jumps = [{ operator: LogicalOperator.AND, conditions: [{ fieldId: 'e', fieldType: FieldTypes.EMAIL, comparison: Comparison.IS_NOT_EMPTY, value: '' }], target: 'gone' }];
        const status = pageStatus(
            slide(
                [
                    { id: 'e', type: FieldTypes.EMAIL, title: 'Email' },
                    { id: 'w', type: FieldTypes.EMAIL, title: 'Work email', properties: { whyWeAsk: 'To reply' } },
                    { id: 'i', type: FieldTypes.SHORT_TEXT, title: 'Ref', internal: true }
                ],
                jumps
            ),
            new Set(['p'])
        );
        expect(status).toMatchObject({ empty: false, hasLogic: true, brokenJumps: 1, missingWhyWeAsk: 1, internal: 1 });
    });
});

describe('names and filtering', () => {
    it('a page is named by its section title, else by its number', () => {
        expect(outlinePageName({ properties: { sectionTitle: ' About you ' } } as StandardFormFieldDto, 0)).toBe('About you');
        expect(outlinePageName({ properties: {} } as StandardFormFieldDto, 2)).toBe('Page 3');
    });

    it('matches plain-text titles case-insensitively', () => {
        const field = { id: 'x', type: FieldTypes.SHORT_TEXT, title: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Your Postcode' }] }] } } as any;
        expect(questionMatches(field, 'postc')).toBe(true);
        expect(questionMatches(field, 'city')).toBe(false);
        expect(questionMatches(field, '  ')).toBe(true);
    });
});

import { describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { Comparison, JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import { ANSWERS, COLOUR_CHOICES, FORM, FRUIT_CHOICES, PAGE_ONE } from '@app/test/response-fixtures';

import { answered, choiceRows, responsePageSections, responsePageUrl, responsesListUrl, themeWithDefaults } from './response-page';

describe('response page urls', () => {
    it('hold the response id only, encoded', () => {
        expect(responsePageUrl('acme', 'form-1', 'r1')).toBe('/acme/dashboard/forms/form-1/responses/r1');
        expect(responsePageUrl('acme', 'form-1', 'a/b?c=d#e')).toBe('/acme/dashboard/forms/form-1/responses/a%2Fb%3Fc%3Dd%23e');
        expect(responsesListUrl('acme', 'form-1')).toBe('/acme/dashboard/forms/form-1/responses');
    });
});

describe('themeWithDefaults', () => {
    it('keeps a form theme as it is and fills the colours of a form without one', () => {
        expect(themeWithDefaults(FORM.theme)).toMatchObject({ primary: FORM.theme!.primary, bodyFont: 'atkinson-next' });
        expect(themeWithDefaults(undefined)).toMatchObject({ primary: '#101828', accent: '#FFFFFF' });
        expect(themeWithDefaults({ primary: '#000000' } as any).secondary).toBe('#1649E2');
    });
});

describe('choiceRows', () => {
    const colour = PAGE_ONE.find((field) => field.id === 'colour')!;
    const fruit = PAGE_ONE.find((field) => field.id === 'fruit')!;

    it('lists every option and marks the chosen one by its id', () => {
        const rows = choiceRows(colour, { choice: { value: COLOUR_CHOICES[0].id } }, false);
        expect(rows.map((row) => [row.label, row.selected])).toEqual([
            ['Red', true],
            ['Green', false],
            ['Blue', false],
            ['Other', false]
        ]);
    });

    it('marks by the option text for an imported answer', () => {
        expect(
            choiceRows(colour, { choice: { value: 'Blue' } }, false)
                .filter((row) => row.selected)
                .map((row) => row.label)
        ).toEqual(['Blue']);
    });

    it('adds the respondent "Other" words as a marked row', () => {
        const rows = choiceRows(colour, { choice: { other: ' Teal ' } }, false);
        expect(rows[rows.length - 1]).toMatchObject({ label: 'Teal', selected: true, other: true });
    });

    it('marks several for a multi-select, "Other" included', () => {
        const rows = choiceRows(fruit, { choices: { values: [FRUIT_CHOICES[0].id, FRUIT_CHOICES[1].id], other: 'Fig' } }, true);
        expect(rows.filter((row) => row.selected).map((row) => row.label)).toEqual(['Apple', 'Pear', 'Fig']);
    });

    it('names an option without text "Item n", like the form', () => {
        const unnamed: any = { ...colour, properties: { choices: [{ id: 'x', value: '' }] } };
        expect(choiceRows(unnamed, {}, false)[0].label).toBe('Item 1');
    });
});

describe('answered', () => {
    it('counts 0 and false, not an empty text or an empty group', () => {
        expect(answered({ number: 0 })).toBe(true);
        expect(answered({ boolean: false })).toBe(true);
        expect(answered({ text: '' })).toBe(false);
        expect(answered(undefined)).toBe(false);
        expect(answered({ items: [] })).toBe(false);
        expect(answered(ANSWERS.guests)).toBe(true);
    });
});

describe('responsePageSections', () => {
    const jumpTo = (target: string) => ({ operator: LogicalOperator.AND, target, conditions: [{ fieldId: 'agree', fieldType: FieldTypes.YES_NO, comparison: Comparison.IS_EQUAL, value: 'Yes' }] });
    const withJump = (target: string) => ({ ...FORM, fields: FORM.fields.map((slide) => (slide.id === 'p1' ? { ...slide, properties: { ...slide.properties, jumps: [jumpTo(target)] } } : slide)) }) as any;

    it('visits every page of a form without jumps', () => {
        expect(responsePageSections(FORM, {}).map((section) => [section.number, section.visited])).toEqual([
            [1, true],
            [2, true],
            [3, true]
        ]);
    });

    it('marks the page a jump skipped, with the same rules the respondent ran', () => {
        expect(responsePageSections(withJump('p3'), { agree: ANSWERS.agree }).map((section) => section.visited)).toEqual([true, false, true]);
        // the rule does not match this answer: no page is skipped
        expect(responsePageSections(withJump('p3'), { agree: { ...ANSWERS.agree, boolean: false } }).map((section) => section.visited)).toEqual([true, true, true]);
    });

    it('marks everything after a jump to submit', () => {
        expect(responsePageSections(withJump(JUMP_TARGET_SUBMIT), { agree: ANSWERS.agree }).map((section) => section.visited)).toEqual([true, false, false]);
    });

    it('shows an imported form as one page', () => {
        const sections = responsePageSections({ formId: 'g', builderVersion: 'v1', settings: { provider: 'google' }, fields: [{ id: 'q', type: FieldTypes.SHORT_TEXT, title: 'x' }] } as any, {});
        expect(sections).toHaveLength(1);
        expect(sections[0].page.properties?.fields).toHaveLength(1);
    });
});

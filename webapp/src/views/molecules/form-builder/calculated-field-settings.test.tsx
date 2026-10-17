import React, { useState } from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import CalculatedFieldSettings, { openReference, suggestionsFor } from '@app/views/molecules/form-builder/calculated-field-settings';

const field = (id: string, type: string, title: string, properties: any = {}): StandardFormFieldDto => ({ id, index: 0, type, title, properties: { fields: [], ...properties } });

function Harness({ expression, onChange }: { expression?: any; onChange?: (property: string, value: unknown) => void }) {
    const [calc, setCalc] = useState(field('total', FieldTypes.CALCULATED, 'Total', { expression }));
    const slides = [{ id: 'p', index: 0, type: FieldTypes.SLIDE, properties: { fields: [field('qty', FieldTypes.NUMBER, 'Quantity'), field('price', FieldTypes.NUMBER, 'Price'), calc] } }] as StandardFormFieldDto[];
    return (
        <CalculatedFieldSettings
            field={calc}
            slides={slides}
            hiddenNames={['utm']}
            onChange={(property, value) => {
                onChange?.(property, value);
                setCalc((previous) => ({ ...previous, properties: { ...previous.properties, [property]: value } }));
            }}
        />
    );
}

describe('the formula input', () => {
    it('shows the stored formula with labels and a preview with sample answers', () => {
        render(<Harness expression={{ '*': [{ var: 'qty' }, { var: 'price' }] }} />);
        expect((screen.getByLabelText('Formula') as HTMLTextAreaElement).value).toBe('{Quantity} * {Price}');
        // sample numbers are 10
        expect(screen.getByTestId('calculation-preview').textContent).toBe('100');
    });

    it('saves a valid formula as an AST', () => {
        const changes: Array<[string, unknown]> = [];
        render(<Harness onChange={(p, v) => changes.push([p, v])} />);
        fireEvent.change(screen.getByLabelText('Formula'), { target: { value: 'round({Price} * 1.21, 2)', selectionStart: 24 } });
        expect(changes.at(-1)).toEqual(['expression', { round: [{ '*': [{ var: 'price' }, 1.21] }, 2] }]);
        expect(screen.getByTestId('calculation-preview').textContent).toBe('12.1');
    });

    it('shows a parse error at its position and keeps the stored formula', () => {
        const changes: Array<[string, unknown]> = [];
        render(<Harness expression={{ var: 'qty' }} onChange={(p, v) => changes.push([p, v])} />);
        const input = screen.getByLabelText('Formula');
        fireEvent.change(input, { target: { value: '{Quantity} * {Height}', selectionStart: 21 } });
        const alert = screen.getByRole('alert');
        expect(alert.textContent).toMatch(/Height/);
        expect(alert.textContent).toMatch(/at character 14/);
        expect(alert.querySelector('mark')?.textContent).toBe('{Height}');
        expect(input.getAttribute('aria-invalid')).toBe('true');
        expect(changes).toEqual([]);
    });

    it('autocompletes field references after {', () => {
        const changes: Array<[string, unknown]> = [];
        render(<Harness onChange={(p, v) => changes.push([p, v])} />);
        const input = screen.getByLabelText('Formula') as HTMLTextAreaElement;
        fireEvent.change(input, { target: { value: '2 * {Pr', selectionStart: 7 } });
        const options = Array.from(screen.getByRole('listbox').querySelectorAll('[role=option]'));
        expect(options.map((o) => o.textContent)).toEqual(['Priceanswer']);
        expect(input.getAttribute('aria-expanded')).toBe('true');
        fireEvent.keyDown(input, { key: 'Enter' });
        expect(input.value).toBe('2 * {Price}');
        expect(changes.at(-1)).toEqual(['expression', { '*': [2, { var: 'price' }] }]);
        expect(screen.queryByRole('listbox')).toBeNull();
    });

    it('sets the format and the visibility', () => {
        const changes: Array<[string, unknown]> = [];
        render(<Harness expression={{ var: 'qty' }} onChange={(p, v) => changes.push([p, v])} />);
        fireEvent.change(screen.getByLabelText('Show as'), { target: { value: 'currency' } });
        expect(changes.at(-1)).toEqual(['format', { style: 'currency', currency: 'EUR' }]);
        expect(screen.getByTestId('calculation-preview').textContent).toBe('€10.00');
        fireEvent.click(screen.getByLabelText('Hide from respondents'));
        expect(changes.at(-1)).toEqual(['hiddenFromRespondents', true]);
    });
});

describe('reference helpers', () => {
    it('finds the open reference at the caret, not inside text', () => {
        expect(openReference('1 + {Pri', 8)).toEqual({ start: 4, query: 'Pri' });
        expect(openReference('{Price} + 1', 11)).toBeNull();
        expect(openReference('concat("{x', 10)).toBeNull();
    });

    it('ranks labels that start with the query first', () => {
        const variables = [
            { key: 'a', label: 'Total price', kind: 'field' as const },
            { key: 'b', label: 'Price', kind: 'field' as const }
        ];
        expect(suggestionsFor(variables, 'pri').map((v) => v.key)).toEqual(['b', 'a']);
    });
});

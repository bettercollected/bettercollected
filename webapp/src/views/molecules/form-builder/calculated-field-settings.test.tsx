import React, { useState } from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { store } from '@app/store/store';
import { calculationVariables } from '@app/utils/calculated-fields';
import AnswerRulesSettings from '@app/views/molecules/form-builder/answer-rules-settings';
import CalculatedFieldSettings, { FORMULA_IDLE_MS, firstQuestionKey, isIncompleteError, openReference, suggestionsFor } from '@app/views/molecules/form-builder/calculated-field-settings';

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

    it('keeps the unfinished-reference error back while suggestions are open', () => {
        render(<Harness />);
        const input = screen.getByLabelText('Formula') as HTMLTextAreaElement;
        fireEvent.change(input, { target: { value: '2 * {Pr', selectionStart: 7 } });
        expect(screen.getByRole('listbox')).toBeTruthy();
        expect(screen.queryByRole('alert')).toBeNull();
        expect(input.getAttribute('aria-invalid')).toBeNull();
        // the list hangs from the input, not from the whole block with the preview
        expect(screen.getByRole('listbox').parentElement).toBe(input.parentElement);
        fireEvent.keyDown(input, { key: 'Escape' });
        expect(screen.getByRole('alert').textContent).toBeTruthy();
    });

    it('previews one unanswered question, counted as 0 or not', () => {
        const changes: Array<[string, unknown]> = [];
        render(<Harness expression={{ '+': [{ var: 'qty' }, { var: 'price' }] }} onChange={(p, v) => changes.push([p, v])} />);
        expect(screen.getByTestId('calculation-preview').textContent).toBe('20');
        expect(screen.getByTestId('calculation-preview-empty').textContent).toBe('Without an answer to Quantity: 10');
        const toggle = screen.getByLabelText('Treat unanswered as 0');
        expect(toggle.getAttribute('aria-checked')).toBe('true');
        fireEvent.click(toggle);
        expect(changes.at(-1)).toEqual(['unansweredAsZero', false]);
        expect(screen.getByTestId('calculation-preview-empty').textContent).toBe('Without an answer to Quantity: no value');
    });

    it('gives the selects room for their text (no global select padding)', () => {
        render(<Harness expression={{ var: 'qty' }} />);
        expect(screen.getByLabelText('Show as').className).toContain('py-0');
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

describe('errors of an unfinished formula', () => {
    afterEach(() => vi.useRealTimers());

    it('wait until typing pauses, or the input is left', () => {
        vi.useFakeTimers();
        render(<Harness />);
        const input = screen.getByLabelText('Formula');
        fireEvent.change(input, { target: { value: 'round({Price}', selectionStart: 13 } });
        expect(screen.queryByRole('alert')).toBeNull();
        act(() => vi.advanceTimersByTime(FORMULA_IDLE_MS - 100));
        expect(screen.queryByRole('alert')).toBeNull();
        act(() => vi.advanceTimersByTime(200));
        expect(screen.getByRole('alert').textContent).toMatch(/Expected/);
        fireEvent.change(input, { target: { value: 'round({Price}, ', selectionStart: 15 } });
        expect(screen.queryByRole('alert')).toBeNull();
        fireEvent.blur(input);
        expect(screen.getByRole('alert')).toBeTruthy();
    });

    it('a mistake inside the formula shows at once', () => {
        vi.useFakeTimers();
        render(<Harness />);
        fireEvent.change(screen.getByLabelText('Formula'), { target: { value: '{Price} = 2 + 1', selectionStart: 15 } });
        expect(screen.getByRole('alert').textContent).toMatch(/==/);
    });

    it('tells an unfinished formula from a mistake', () => {
        expect(isIncompleteError('round({Price}', { start: 13 })).toBe(true);
        expect(isIncompleteError('round({Price}  ', { start: 13 })).toBe(true);
        expect(isIncompleteError('{Price} = 2', { start: 8 })).toBe(false);
    });
});

describe('a hidden calculation piped into respondent text', () => {
    it('is warned about in the inspector', () => {
        const calc = field('risk', FieldTypes.CALCULATED, 'Risk', { expression: 1, hiddenFromRespondents: true });
        const slides = [{ id: 'p', index: 0, type: FieldTypes.SLIDE, properties: { fields: [calc, { ...field('q', FieldTypes.SHORT_TEXT, 'Why?'), description: 'Your risk is {{field:risk}}' }] } }] as StandardFormFieldDto[];
        render(<CalculatedFieldSettings field={calc} slides={slides} hiddenNames={[]} onChange={() => {}} />);
        expect(screen.getByTestId('hidden-piped-warning').textContent).toMatch(/piped into the description of question 2 on page 1 \(“Why\?”\)/);
    });

    it('is not warned about when nothing pipes it', () => {
        render(<Harness expression={1} />);
        expect(screen.queryByTestId('hidden-piped-warning')).toBeNull();
    });
});

describe('the suggestion list', () => {
    it('opens in flow, about five rows high, so it does not cover the preview', () => {
        render(<Harness />);
        fireEvent.change(screen.getByLabelText('Formula'), { target: { value: '{', selectionStart: 1 } });
        const list = screen.getByRole('listbox');
        expect(list.className).not.toMatch(/\babsolute\b/);
        expect(list.className).toContain('max-h-[148px]');
        expect(list.className).toContain('overflow-auto');
    });
});

describe('the preview without an answer', () => {
    it('finds the first question through other calculations', () => {
        const slides = [
            {
                id: 'p',
                index: 0,
                type: FieldTypes.SLIDE,
                properties: {
                    fields: [
                        field('qty', FieldTypes.NUMBER, 'Quantity'),
                        field('sub', FieldTypes.CALCULATED, 'Subtotal', { expression: { '*': [{ var: 'qty' }, 2] } }),
                        field('vat', FieldTypes.CALCULATED, 'VAT', { expression: { '*': [{ var: 'sub' }, 0.21] } })
                    ]
                }
            }
        ] as StandardFormFieldDto[];
        const variables = calculationVariables(slides);
        expect(firstQuestionKey({ '+': [{ var: 'vat' }, { var: 'sub' }] }, variables, slides)?.label).toBe('Quantity');
        expect(firstQuestionKey({ '+': [1, 2] }, variables, slides)).toBeUndefined();
    });
});

describe('the short-text Format select', () => {
    it('has room for its text too', () => {
        render(
            <ReduxProvider store={store}>
                <AnswerRulesSettings field={field('name', FieldTypes.SHORT_TEXT, 'Name')} onChange={() => {}} />
            </ReduxProvider>
        );
        expect(screen.getByLabelText('Format').className).toContain('py-0');
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

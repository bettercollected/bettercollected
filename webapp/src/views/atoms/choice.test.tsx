// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { FormFieldComponent } from '@app/views/organism/form/form-slide';

import Choice from './choice';

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const choices = (...values: string[]) => values.map((value, i) => ({ id: `choice-${i}`, value }));
const field = (overrides: Partial<StandardFormFieldDto['properties']> = {}): StandardFormFieldDto => ({
    id: 'colour',
    index: 0,
    type: FieldTypes.MULTIPLE_CHOICE,
    title: 'Favourite colour',
    properties: { fields: [], choices: choices('Red', 'Green', 'Blue'), ...overrides }
});

const renderField = (f: StandardFormFieldDto) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <FormFieldComponent field={f} slideIndex={0} />
            </Provider>
        </ReduxProvider>
    );

describe('choice controls', () => {
    it('a single-answer question is a radio group named by its question', () => {
        renderField(field());
        const group = screen.getByRole('radiogroup', { name: 'Favourite colour' });
        expect(group).toBeDefined();
        const radios = screen.getAllByRole('radio');
        expect(radios.map((r) => r.textContent)).toEqual(['Red', 'Green', 'Blue']);
        act(() => {
            fireEvent.click(radios[1]);
        });
        expect(screen.getByRole('radio', { name: 'Green' }).getAttribute('aria-checked')).toBe('true');
        expect(screen.getByRole('radio', { name: 'Red' }).getAttribute('aria-checked')).toBe('false');
    });

    it('a several-answers question is a list of checkboxes, with its hint', () => {
        renderField(field({ allowMultipleSelection: true }));
        expect(screen.getByText('Choose as many as you like.')).toBeDefined();
        const boxes = screen.getAllByRole('checkbox');
        expect(boxes).toHaveLength(3);
        act(() => {
            fireEvent.click(boxes[0]);
        });
        act(() => {
            fireEvent.click(screen.getAllByRole('checkbox')[2]);
        });
        expect(screen.getAllByRole('checkbox').map((b) => b.getAttribute('aria-checked'))).toEqual(['true', 'false', 'true']);
    });

    it('selection shows in the control and the weight, not only in colour', () => {
        const theme = { title: 'T', primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB' };
        const { rerender, container } = render(<Choice choice={{ id: 'a', value: 'A' }} index={0} theme={theme} kind="checkbox" />);
        const button = screen.getByRole('checkbox', { name: 'A' });
        expect(button.className).not.toContain('font-semibold');
        expect(container.querySelector('[data-choice-indicator] svg')).toBeNull();
        rerender(<Choice choice={{ id: 'a', value: 'A' }} index={0} theme={theme} kind="checkbox" isSelected />);
        expect(screen.getByRole('checkbox', { name: 'A' }).className).toContain('font-semibold');
        // The box carries a tick once chosen.
        expect(container.querySelector('[data-choice-indicator] svg')).not.toBeNull();
    });

    it('rows are at least 48px tall', () => {
        render(<Choice choice={{ id: 'a', value: 'A' }} index={0} />);
        expect(screen.getByRole('button', { name: 'A' }).className).toContain('min-h-12');
    });
});

describe('radio group keyboard', () => {
    it('arrow keys move the choice and the single tab stop', () => {
        renderField(field());
        const [red] = screen.getAllByRole('radio');
        expect(screen.getAllByRole('radio').map((r) => r.getAttribute('tabindex'))).toEqual(['0', '-1', '-1']);
        act(() => {
            fireEvent.keyDown(red, { key: 'ArrowDown' });
        });
        expect(screen.getByRole('radio', { name: 'Green' }).getAttribute('aria-checked')).toBe('true');
        expect(screen.getAllByRole('radio').map((r) => r.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
        act(() => {
            fireEvent.keyDown(screen.getByRole('radio', { name: 'Green' }), { key: 'ArrowUp' });
        });
        act(() => {
            fireEvent.keyDown(screen.getByRole('radio', { name: 'Red' }), { key: 'ArrowUp' });
        });
        // Wraps from the first option to the last.
        expect(screen.getByRole('radio', { name: 'Blue' }).getAttribute('aria-checked')).toBe('true');
    });

    it('yes/no is a labelled radio group too', () => {
        renderField({ id: 'yn', index: 0, type: FieldTypes.YES_NO, title: 'Coming back?' });
        expect(screen.getByRole('radiogroup', { name: 'Coming back?' })).toBeDefined();
    });
});

// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';
import { FormFieldComponent } from '@app/views/organism/form/form-slide';

import Choice, { initialKeys, optionKeys, showsOptionKeys } from './choice';

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

/** The field on a page that wears `theme` (the form's theme, as the respondent page sets it). */
function Themed({ theme, children }: { theme: FormTheme; children: React.ReactNode }) {
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(theme, { undoable: false });
    }, [theme]);
    return <>{children}</>;
}

const renderThemed = (f: StandardFormFieldDto, theme: FormTheme) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Themed theme={theme}>
                    <FormFieldComponent field={f} slideIndex={0} />
                </Themed>
            </Provider>
        </ReduxProvider>
    );

const KANTLIJN = ThemeColors.find((theme) => theme.title === 'Kantlijn')!;
const DEFAULT = ThemeColors.find((theme) => theme.title === 'Default')!;

describe('lettered option cards', () => {
    it('a theme with its own corners letters its options and names the keys', () => {
        expect(showsOptionKeys(KANTLIJN)).toBe(true);
        renderThemed(field(), KANTLIJN);
        const radios = screen.getAllByRole('radio');
        expect(radios.map((r) => r.getAttribute('aria-keyshortcuts'))).toEqual(['A', 'B', 'C']);
        // The letter is decoration: the option's name is its label alone.
        expect(screen.getByRole('radio', { name: 'Green' })).toBeDefined();
        expect(document.querySelectorAll('[data-option-key-hint]')).toHaveLength(3);
        expect(document.querySelector('[data-choice-indicator]')).toBeNull();
    });

    it('a theme without corners of its own is drawn as before: no letters, no shortcuts', () => {
        expect(showsOptionKeys(DEFAULT)).toBe(false);
        expect(showsOptionKeys({ ...KANTLIJN, radius: null } as unknown as FormTheme)).toBe(false);
        renderThemed(field(), DEFAULT);
        expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-keyshortcuts'))).toEqual([null, null, null]);
        expect(document.querySelector('[data-option-key-hint]')).toBeNull();
        expect(document.querySelectorAll('[data-choice-indicator]')).toHaveLength(3);
        // A letter does nothing there.
        act(() => void fireEvent.keyDown(screen.getAllByRole('radio')[0], { key: 'b' }));
        expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-checked'))).toEqual(['false', 'false', 'false']);
    });

    it('a letter chooses its option and takes focus there; the chosen card ends in a check mark', () => {
        renderThemed(field(), KANTLIJN);
        expect(document.querySelector('[data-choice-check]')).toBeNull();
        act(() => void fireEvent.keyDown(screen.getAllByRole('radio')[0], { key: 'c' }));
        const blue = screen.getByRole('radio', { name: 'Blue' });
        expect(blue.getAttribute('aria-checked')).toBe('true');
        expect(document.activeElement).toBe(blue);
        expect(blue.querySelector('[data-choice-check]')).not.toBeNull();
        expect(document.querySelectorAll('[data-choice-check]')).toHaveLength(1);
        // Arrow keys still move as before.
        act(() => void fireEvent.keyDown(blue, { key: 'ArrowDown' }));
        expect(screen.getByRole('radio', { name: 'Red' }).getAttribute('aria-checked')).toBe('true');
    });

    it('letters with a modifier, and letters past the list, are left alone', () => {
        renderThemed(field(), KANTLIJN);
        const [red] = screen.getAllByRole('radio');
        act(() => void fireEvent.keyDown(red, { key: 'b', ctrlKey: true }));
        act(() => void fireEvent.keyDown(red, { key: 'b', altKey: true }));
        act(() => void fireEvent.keyDown(red, { key: 'b', metaKey: true }));
        act(() => void fireEvent.keyDown(red, { key: 'z' }));
        expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-checked'))).toEqual(['false', 'false', 'false']);
    });

    it('in a several-answers list a letter ticks and unticks its option', () => {
        renderThemed(field({ allowMultipleSelection: true }), KANTLIJN);
        const boxes = () => screen.getAllByRole('checkbox');
        expect(boxes().map((b) => b.getAttribute('aria-keyshortcuts'))).toEqual(['A', 'B', 'C']);
        act(() => void fireEvent.keyDown(boxes()[0], { key: 'b' }));
        act(() => void fireEvent.keyDown(boxes()[1], { key: 'C' }));
        expect(boxes().map((b) => b.getAttribute('aria-checked'))).toEqual(['false', 'true', 'true']);
        expect(document.activeElement).toBe(boxes()[2]);
        act(() => void fireEvent.keyDown(boxes()[2], { key: 'b' }));
        expect(boxes().map((b) => b.getAttribute('aria-checked'))).toEqual(['false', 'false', 'true']);
        expect(document.querySelectorAll('[data-choice-check]')).toHaveLength(1);
    });

    it('yes/no is lettered by its own initials', () => {
        renderThemed({ id: 'yn', index: 0, type: FieldTypes.YES_NO, title: 'Coming back?' }, KANTLIJN);
        expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-keyshortcuts'))).toEqual(['Y', 'N']);
        act(() => void fireEvent.keyDown(screen.getAllByRole('radio')[0], { key: 'n' }));
        expect(screen.getByRole('radio', { name: 'No' }).getAttribute('aria-checked')).toBe('true');
    });

    it('initials stand in only when they are distinct letters', () => {
        expect(initialKeys(['Ja', 'Nee'])).toEqual(['J', 'N']);
        expect(initialKeys(['Nope', 'No'])).toEqual(['A', 'B']);
        expect(initialKeys(['1 time', 'Never'])).toEqual(['A', 'B']);
        expect(optionKeys(28).slice(24)).toEqual(['Y', 'Z', undefined, undefined]);
    });
});

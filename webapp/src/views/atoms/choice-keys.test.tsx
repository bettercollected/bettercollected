import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { FormTheme, THEME_CHOICE_KEYS, ThemeColors, themeProblems, themeTypeShape } from '@app/constants/theme';
import { applyOps } from '@app/lib/form-ops';
import { contrast } from '@app/utils/color-contrast';

import Choice, { CHOICE_KEY_FILLS, choiceKeyColours, choiceRowStyle, hasChoiceKeys, optionKeys, showsOptionKeys } from './choice';
import ChoiceRadioGroup from './choice-radio-group';

/**
 * The `choiceKeys` theme key: lettered keys on the answer options, small squares with an
 * ink letter on a flat pigment, the chosen row solid in the action colour with white text
 * and a check. The pigments are the form's own constants (a respondent page never reads
 * the app's variables). Nothing uses it yet: a fixture theme drives these tests.
 */

const PLAIN: FormTheme = { title: 'Plain', primary: '#1A1238', secondary: '#4B35DB', tertiary: '#7C7396', accent: '#FBF7F1' };
const LETTERED: FormTheme = { ...PLAIN, title: 'Lettered', choiceKeys: 'letters' };

const options = ['North', 'South', 'East', 'West', 'Centre', 'Online'].map((label, index) => ({ value: `v${index}`, label, key: `k${index}` }));

const renderGroup = (theme: FormTheme, value: string | null = null, onChange = vi.fn()) => render(<ChoiceRadioGroup options={options} value={value} onChange={onChange} theme={theme} labelledBy="q" />);

describe('the key', () => {
    it('is a list of one value, valid or absent, checked like the other listed keys', () => {
        expect(THEME_CHOICE_KEYS).toEqual(['letters']);
        expect(themeProblems({ ...PLAIN })).toEqual([]);
        expect(themeProblems({ ...LETTERED })).toEqual([]);
        expect(themeProblems({ ...PLAIN, choiceKeys: null })).toEqual([]);
        expect(themeProblems({ ...PLAIN, choiceKeys: 'numbers' })).toEqual(['theme.choiceKeys must be one of: letters.']);
    });

    it('is carried over when a custom theme is made from this one, and only the Pigment preset sets it', () => {
        expect(themeTypeShape(LETTERED)).toEqual({ choiceKeys: 'letters' });
        expect(themeTypeShape(PLAIN)).toEqual({});
        // only the Pigment presets set it (behind their one switch): Pigment and its Leaflet blend
        expect(ThemeColors.filter((preset) => preset.choiceKeys != null).map((preset) => preset.title)).toEqual(['Pigment', 'Pigment Leaflet']);
    });

    it('is taken or refused by the edit engine, as the backend does', () => {
        const doc = { title: 'F', builderVersion: 'v2', fields: [] } as any;
        const ok = applyOps(doc, [{ op: 'update_theme', theme: { ...LETTERED } }] as any);
        expect(ok.results[0].ok).toBe(true);
        expect((ok.doc as any).theme.choiceKeys).toBe('letters');
        const refused = applyOps(doc, [{ op: 'update_theme', theme: { ...PLAIN, choiceKeys: 'numbers' } }] as any);
        expect(refused.results[0].ok).toBe(false);
        expect(refused.results[0].message).toBe('theme.choiceKeys must be one of: letters.');
    });
});

describe('a theme without the key', () => {
    it('shows no keys unless it sets a corner, as before', () => {
        expect(hasChoiceKeys(PLAIN)).toBe(false);
        expect(showsOptionKeys(PLAIN)).toBe(false);
        expect(showsOptionKeys({ ...PLAIN, radius: 'soft' })).toBe(true);
        const { container } = renderGroup(PLAIN, 'v1');
        expect(container.querySelector('[data-option-key-hint]')).toBeNull();
        expect(container.querySelector('[data-choice-key]')).toBeNull();
    });

    it('keeps the plain keys of a theme with a corner (outlined, no pigment)', () => {
        const { container } = renderGroup({ ...PLAIN, radius: 'soft' }, 'v1');
        expect(container.querySelectorAll('[data-option-key-hint]')).toHaveLength(6);
        expect(container.querySelector('[data-choice-key]')).toBeNull();
    });
});

describe('a theme with the key', () => {
    it('puts a lettered square on each option, A to F, in the pigments in turn', () => {
        const { container } = renderGroup(LETTERED);
        const keys = Array.from(container.querySelectorAll<HTMLElement>('[data-choice-key]'));
        expect(keys.map((key) => key.textContent)).toEqual(optionKeys(6));
        expect(keys.map((key) => key.style.background)).toEqual(['#FF8A73', '#FFC62E', '#5FD9B0', '#6BBEF7', '#D9A0FF', '#FF8A73'].map((hex) => hexToRgb(hex)));
    });

    it('draws each letter in ink that holds 4.5:1 on its pigment, for the theme and for an unreadable ink', () => {
        CHOICE_KEY_FILLS.forEach((fill, index) => {
            const { ink } = choiceKeyColours(LETTERED, index);
            expect(ink).toBe('#1A1238');
            expect(contrast(ink, fill)).toBeGreaterThanOrEqual(4.5);
            // a pale ink that would not read falls back to black, which does
            const fallback = choiceKeyColours({ ...LETTERED, primary: '#E8E4FF' }, index);
            expect(fallback.ink).toBe('#000000');
            expect(contrast(fallback.ink, fill)).toBeGreaterThanOrEqual(4.5);
        });
        expect(CHOICE_KEY_FILLS).toHaveLength(5);
    });

    it('keeps the key out of the accessible name: the option is named by its label', () => {
        renderGroup(LETTERED, 'v1');
        expect(screen.getByRole('radio', { name: 'North' })).toBeInTheDocument();
        expect(screen.getAllByRole('radio').map((radio) => radio.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false', 'false', 'false', 'false']);
        for (const key of document.querySelectorAll('[data-choice-key]')) expect(key.getAttribute('aria-hidden')).toBe('true');
    });

    it('fills the chosen row with the action colour, white text and a check (shape as well as colour)', () => {
        const { container } = renderGroup(LETTERED, 'v1');
        const chosen = screen.getByRole('radio', { name: 'South' });
        expect(choiceRowStyle(LETTERED, true).solid).toBe(true);
        expect(choiceRowStyle(LETTERED, false).solid).toBe(false);
        // the solid fill and its ink are variables with the theme's own colours as the fallback (theme-root.ts)
        expect(chosen.style.background).toBe('var(--form-highlight-solid, #4B35DB)');
        expect(chosen.style.color).toBe('var(--form-highlight-solid-ink, #ffffff)');
        expect(chosen.querySelector('[data-choice-check]')).not.toBeNull();
        expect(container.querySelectorAll('[data-choice-check]')).toHaveLength(1);
        // the chosen key keeps its pigment
        expect((chosen.querySelector('[data-choice-key]') as HTMLElement).style.background).toBe(hexToRgb('#FFC62E'));
    });

    it('shows the keys with the Leaflet style but no solid chosen row: the bold label and the check mark it (documented)', () => {
        const leaflet = { ...LETTERED, style: 'leaflet' as const };
        const { container } = renderGroup(leaflet, 'v1');
        const chosen = screen.getByRole('radio', { name: 'South' });
        expect(choiceRowStyle(leaflet, true).solid).toBe(false);
        expect(container.querySelectorAll('[data-choice-key]')).toHaveLength(6);
        expect(chosen.style.background).not.toContain('--form-highlight-solid');
        expect(chosen.className).toContain('font-semibold');
        expect(chosen.querySelector('[data-choice-check]')).not.toBeNull();
    });

    it('does not read the app theme: the colours are the form theme and constants only', () => {
        const { container } = renderGroup(LETTERED, 'v1');
        expect(container.innerHTML).not.toMatch(/--app-|var\(--(?:color-|pig-|action|canvas|surface)/);
    });

    it('works on checkboxes too: a lettered key, a solid chosen row, a check, the role of a checkbox', () => {
        render(
            <div>
                {options.slice(0, 3).map((option, index) => (
                    <Choice key={option.key} kind="checkbox" isSelected={index === 0} theme={LETTERED} choice={{ id: option.key, value: option.label }} index={index} keyHint={optionKeys(3)[index]} onClick={() => {}} />
                ))}
            </div>
        );
        expect(screen.getAllByRole('checkbox')).toHaveLength(3);
        expect(screen.getByRole('checkbox', { name: 'North' })).toHaveAttribute('aria-checked', 'true');
        expect(document.querySelectorAll('[data-choice-key]')).toHaveLength(3);
        expect(document.querySelectorAll('[data-choice-check]')).toHaveLength(1);
    });
});

describe('the letters, as the keys of a theme with a corner already work', () => {
    it('choose the option when pressed on an option, as option keys do today (nothing new)', () => {
        const onChange = vi.fn();
        renderGroup(LETTERED, null, onChange);
        fireEvent.keyDown(screen.getByRole('radio', { name: 'North' }), { key: 'c' });
        expect(onChange).toHaveBeenCalledWith('v2', { viaKeys: true });
    });

    it('do nothing on a theme without keys, and never in a text field', () => {
        const onChange = vi.fn();
        renderGroup(PLAIN, null, onChange);
        fireEvent.keyDown(screen.getByRole('radio', { name: 'North' }), { key: 'c' });
        expect(onChange).not.toHaveBeenCalled();
    });
});

function hexToRgb(hex: string): string {
    const n = parseInt(hex.slice(1), 16);
    return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

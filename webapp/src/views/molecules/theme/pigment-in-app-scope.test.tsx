// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import AppThemeScope from '@app/components/app-theme/app-theme-scope';
import { FormTheme, findPreset } from '@app/constants/theme';
import { Button } from '@app/shadcn/components/ui/button';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { colourAt, resolveValue } from '@app/test/app-theme-cascade';
import Choice from '@app/views/atoms/choice';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { formButtonStyle } from './theme-root';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));

// The Pigment preset's iris is the FORM theme's `secondary` (#4B35DB), not an app role: a Pigment-preset form is drawn
// the same on the real respondent page (no scope), in the builder preview of a Daybreak workspace and in the builder
// preview of a Pigment workspace, where the app's own iris must not be what makes it iris.
const PIGMENT = findPreset('Pigment') as FormTheme;
const IRIS = '#4B35DB';
const RING = 'var(--focus-ring, var(--app-focus-ring, var(--color-brand-500)))';

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

const form = (label: string, theme: FormTheme) => (
    <LayoutWrapper theme={theme} disabled showDesktopLayout>
        <Button variant="primary" style={formButtonStyle(theme.secondary, '8px')}>
            {label}
        </Button>
        <Choice isSelected theme={theme} choice={{ id: 'c1', value: `${label} option` }} index={0} keyHint="A" keyIndex={0} />
    </LayoutWrapper>
);

/** What a form draws, resolved where it is drawn: the button, the chosen row, a key and the focus ring. */
const drawn = (label: string) => {
    const button = screen.getByRole('button', { name: label });
    const row = screen.getByRole('button', { name: `${label} option` });
    const key = row.querySelector('[data-choice-key]') as HTMLElement;
    return {
        button: resolveValue(String(button.style.background), button).toUpperCase(),
        buttonInk: resolveValue(String(button.style.color), button).toUpperCase(),
        action: colourAt(button, '--color-app-action'),
        ring: resolveValue(RING, button).toUpperCase(),
        row: resolveValue(String(row.style.background), row).toUpperCase(),
        rowInk: resolveValue(String(row.style.color), row).toLowerCase(),
        key: key.style.background
    };
};

describe('a Pigment-preset form in an app theme scope', () => {
    it('is the same with no scope, in a Daybreak scope and in a Pigment scope, and its iris is the form theme own', () => {
        wrap(
            <>
                {form('Plain', PIGMENT)}
                <AppThemeScope workspaceId="ws-1" initial="daybreak">
                    {form('Daybreak', PIGMENT)}
                </AppThemeScope>
                <AppThemeScope workspaceId="ws-2" initial="pigment">
                    {form('Pigment', PIGMENT)}
                </AppThemeScope>
            </>
        );
        const plain = drawn('Plain');
        // the preset's iris comes from the form theme: the button and the chosen row
        expect(plain.button).toBe(IRIS);
        expect(plain.row).toBe(IRIS);
        expect(plain.rowInk).toBe('#ffffff');
        // ...and nothing differs when the form is drawn inside either scope
        expect(drawn('Daybreak')).toEqual(plain);
        expect(drawn('Pigment')).toEqual(plain);
    });

    it('does not take its iris from the app role: a Daybreak-scope form with the Pigment preset has no app iris', () => {
        wrap(
            <AppThemeScope workspaceId="ws-1" initial="daybreak">
                {form('Daybreak', PIGMENT)}
            </AppThemeScope>
        );
        // the app's blue is not what colours it either: the form theme's secondary is
        expect(drawn('Daybreak').button).toBe(IRIS);
        expect(colourAt(screen.getByRole('button', { name: 'Daybreak' }), '--color-app-action')).not.toBe(IRIS);
    });
});

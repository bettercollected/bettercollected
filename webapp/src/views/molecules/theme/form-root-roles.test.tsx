// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { readFileSync } from 'fs';
import { resolve } from 'path';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import AppThemeScope from '@app/components/app-theme/app-theme-scope';
import { FormTheme } from '@app/constants/theme';
import { APP_ROLES_RESET_ON_FORMS } from '@app/lib/app-theme';
import { Button } from '@app/shadcn/components/ui/button';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { CSS_FILE, colourAt, resolveValue, scopeRule } from '@app/test/app-theme-cascade';
import WelcomePage from '@app/views/organism/form/welcome-page';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { formButtonStyle, formRootProps, themeRootProps } from './theme-root';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));

// A respondent's form is drawn in the form's own colours, in every place it is drawn: the real page (no app theme scope),
// the builder canvas, the preview page and the preview dialog (inside the scope of a Pigment workspace). Whatever app
// role the primary button, the focus outline or a chosen option reads must therefore fall back to the frozen blue on
// the form's root (`formRootProps`), or the preview would show iris where the real page is blue.
const RING = 'var(--focus-ring, var(--app-focus-ring, var(--color-brand-500)))';
const IRIS = '#4B35DB';
const BLUE = { action: '#1649E2', hover: '#123FC9', pressed: '#0E2D8F', on: '#FFFFFF', ring: '#123FC9' };

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

const states = (button: Element) => ({
    action: colourAt(button, '--color-app-action'),
    hover: colourAt(button, '--color-app-action-hover'),
    pressed: colourAt(button, '--color-app-action-pressed'),
    on: colourAt(button, '--color-app-on-action'),
    ring: resolveValue(RING, button).toUpperCase()
});

const noSecondary: FormTheme = { title: 'Plain', primary: '#16261F', tertiary: '#7D8C84', accent: '#FFFFFF' } as FormTheme;
const themed: FormTheme = { title: 'Mine', primary: '#16261F', secondary: '#1E4D3B', tertiary: '#7D8C84', accent: '#FFFFFF', highlight: '#A3305A' };

describe('the app roles on a form root', () => {
    it('is the harness itself: in a Pigment scope but outside a form, the primary button is iris', () => {
        wrap(
            <AppThemeScope workspaceId="ws-1" initial="pigment">
                <Button variant="primary">Outside</Button>
            </AppThemeScope>
        );
        expect(states(screen.getByRole('button', { name: 'Outside' }))).toEqual({ action: IRIS, hover: '#3E29C4', pressed: '#2F1DA2', on: '#FFFFFF', ring: IRIS });
    });

    it.each([
        ['a form with no theme', undefined],
        ['a form whose theme has no secondary', noSecondary]
    ])('draws %s in a Pigment scope with the blue of the real page: the button in each state and the focus ring', (_name, theme) => {
        wrap(
            <AppThemeScope workspaceId="ws-1" initial="pigment">
                <LayoutWrapper theme={theme} disabled showDesktopLayout>
                    <Button variant="primary">Start</Button>
                </LayoutWrapper>
            </AppThemeScope>
        );
        expect(states(screen.getByRole('button', { name: 'Start' }))).toEqual(BLUE);
    });

    it('draws "Verify now" of the welcome page in the blue of the real page inside a Pigment scope', () => {
        store.dispatch(setForm({ formId: 'verify', title: 'Private form', fields: [], settings: { private: true }, welcomePage: {} } as any));
        wrap(
            <AppThemeScope workspaceId="ws-1" initial="pigment">
                <LayoutWrapper theme={undefined} disabled showDesktopLayout>
                    <WelcomePage isPreviewMode />
                </LayoutWrapper>
            </AppThemeScope>
        );
        const verify = screen.getByRole('button', { name: /verify now/i });
        expect(verify.className).toContain('bg-app-action');
        expect(states(verify)).toEqual(BLUE);
    });

    it('keeps the colours of a themed form: its own focus colour and its own button, not the app role', () => {
        wrap(
            <AppThemeScope workspaceId="ws-1" initial="pigment">
                <LayoutWrapper theme={themed} disabled showDesktopLayout>
                    <Button variant="primary" style={formButtonStyle(themed.secondary, '8px')}>
                        Themed
                    </Button>
                </LayoutWrapper>
            </AppThemeScope>
        );
        const button = screen.getByRole('button', { name: 'Themed' });
        expect(resolveValue(RING, button).toUpperCase()).toBe('#A3305A');
        expect(resolveValue(String(formButtonStyle(themed.secondary, '8px').background), button).toUpperCase()).toBe('#1E4D3B');
        expect(colourAt(button, '--color-app-action')).toBe(BLUE.action);
    });

    it('leaves a real respondent page, with no scope, as it was, and is the same inside the Daybreak scope', () => {
        wrap(
            <>
                <LayoutWrapper theme={noSecondary} disabled showDesktopLayout>
                    <Button variant="primary">Plain page</Button>
                </LayoutWrapper>
                <AppThemeScope workspaceId="ws-1" initial="daybreak">
                    <LayoutWrapper theme={noSecondary} disabled showDesktopLayout>
                        <Button variant="primary">Daybreak preview</Button>
                    </LayoutWrapper>
                </AppThemeScope>
            </>
        );
        expect(states(screen.getByRole('button', { name: 'Plain page' }))).toEqual(BLUE);
        expect(states(screen.getByRole('button', { name: 'Daybreak preview' }))).toEqual(BLUE);
    });

    it('draws every chrome utility that has a frozen fallback as the real page does: links, edges, washes, controls, soft fills', () => {
        const inline = CSS_FILE.match(/@theme inline \{([^}]*)\}/)?.[1] ?? '';
        const entries = [...inline.matchAll(/(--color-[\w-]+):\s*var\(--app-[\w-]+,/g)].map((m) => m[1]);
        expect(entries.length).toBeGreaterThan(10);
        // what the real page draws: a document with no scope at all
        const frozen = wrap(<div data-testid="outside" />);
        const real = Object.fromEntries(entries.map((entry) => [entry, colourAt(screen.getByTestId('outside'), entry)]));
        frozen.unmount();
        wrap(
            <AppThemeScope workspaceId="ws-1" initial="pigment">
                <div data-testid="in-scope" />
                <LayoutWrapper theme={undefined} disabled showDesktopLayout>
                    <div data-testid="in-form" />
                </LayoutWrapper>
            </AppThemeScope>
        );
        const inForm = screen.getByTestId('in-form');
        const inScope = screen.getByTestId('in-scope');
        for (const entry of entries) {
            expect(colourAt(inForm, entry), `${entry} on a form root`).toBe(real[entry]);
            // the harness sees the leak: in the scope but outside a form, the roles that differ in Pigment are Pigment's
            if (entry !== '--color-app-on-action') expect(colourAt(inScope, entry), `${entry} in the scope`).not.toBe(real[entry]);
        }
    });

    it('adds nothing to the root of a real respondent page (no scope): its markup is what it always was', () => {
        const { container } = wrap(
            <LayoutWrapper theme={noSecondary} disabled showDesktopLayout>
                <Button variant="primary">Plain page</Button>
            </LayoutWrapper>
        );
        expect(container.innerHTML.match(/style="[^"]*--app-[^"]*"/)?.[0] ?? '').toBe('');
    });
});

describe('formRootProps', () => {
    it('resets every listed role and keeps what the theme sets; themeRootProps itself sets no role', () => {
        const props = formRootProps(themed, true);
        for (const role of APP_ROLES_RESET_ON_FORMS) expect((props.style as Record<string, string>)[role], role).toBe('initial');
        expect((props.style as Record<string, string>)['--focus-ring']).toBe('#A3305A');
        expect(props.attributes).toEqual(themeRootProps(themed).attributes);
        expect(formRootProps(themed, false)).toEqual(themeRootProps(themed));
        expect(Object.keys(formRootProps(undefined, true).style).sort()).toEqual([...APP_ROLES_RESET_ON_FORMS].sort());
        for (const role of APP_ROLES_RESET_ON_FORMS) expect(themeRootProps(themed).style).not.toHaveProperty(role);
    });
});

describe('the list of roles a form root resets', () => {
    const globals = readFileSync(resolve(__dirname, '../../../assets/css/globals.css'), 'utf8');
    // a role read with a fallback is meant to be readable outside a scope, so a respondent component could read it
    const readWithFallback = [...new Set([...(CSS_FILE + globals).matchAll(/var\((--app-[\w-]+),/g)].map((m) => m[1]))];
    // read by html and body only, which sit above every form root (a form root cannot reset what its ancestors paint)
    const ABOVE_THE_FORM = ['--app-canvas'];

    it('covers every app role the stylesheet reads with a frozen fallback', () => {
        const missing = readWithFallback.filter((name) => !ABOVE_THE_FORM.includes(name) && !(APP_ROLES_RESET_ON_FORMS as readonly string[]).includes(name));
        expect(missing).toEqual([]);
    });

    it('names only roles both themes declare', () => {
        for (const theme of ['daybreak', 'pigment']) for (const role of APP_ROLES_RESET_ON_FORMS) expect(scopeRule(theme), `${theme} ${role}`).toHaveProperty([role]);
    });
});

describe('native controls in a Pigment scope', () => {
    it('take the iris on the control itself, not on the scope root, so a form root can undo it', () => {
        // the rule names the controls; the scope's own block never carries `accent-color`
        expect(CSS_FILE).toMatch(/\[data-app-theme='pigment'\] :where\(input\[type='checkbox'\], input\[type='radio'\], input\[type='range'\]\) \{\s*accent-color: var\(--app-primary\);/);
        expect(CSS_FILE).not.toMatch(/^\[data-app-theme='pigment'\] \{[^}]*accent-color/m);
    });

    it('draw a checkbox inside a form root with the browser accent, and one in the app with iris', () => {
        wrap(
            <AppThemeScope workspaceId="ws-1" initial="pigment">
                <input type="checkbox" aria-label="App checkbox" />
                <LayoutWrapper theme={undefined} disabled showDesktopLayout>
                    <input type="checkbox" aria-label="Form checkbox" />
                </LayoutWrapper>
            </AppThemeScope>
        );
        // the control's accent-color is `var(--app-primary)`: iris where the variable is set, invalid (so the browser's own accent) where the form root reset it
        expect(resolveValue('var(--app-primary)', screen.getByLabelText('App checkbox')).toUpperCase()).toBe(IRIS);
        expect(resolveValue('var(--app-primary)', screen.getByLabelText('Form checkbox'))).toBe('');
    });
});

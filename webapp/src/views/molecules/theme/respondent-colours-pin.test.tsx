import { readFileSync } from 'fs';
import { resolve } from 'path';

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it } from 'vitest';

import PoweredBy from '@app/components/ui/powered-by';
import { ThemeColors } from '@app/constants/theme';
import I18nProvider from '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import TrustLayer from '@app/views/molecules/form/trust-layer';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { formButtonStyle, highlightColours, themeRootProps } from './theme-root';

/**
 * Respondent forms must not move when the app's own colours do.
 *
 * A published form wears its stored theme (colours saved inline), and a form with no stored
 * theme wears the Default preset from constants. Two surfaces on a form read the app's own
 * tokens instead: the trust strip and the "Powered by" badge. This file pins, as literal hex
 * values, what all three end up with, so a change to the app's palette (a new canvas, a new
 * ramp, a remapped token) fails here before it can reach a published form.
 */

const css = readFileSync(resolve(__dirname, '../../../assets/css/tailwind.css'), 'utf8');

/** `text` as a literal inside a regular expression: backslashes and every metacharacter escaped. */
const escapeRegExp = (text: string) => text.replace(/[\\^$.*+?()[\]{}|]/g, '\\$&');

/** The `@theme` colour tokens, with `var(--color-x)` aliases followed to their hex. */
function themeColour(name: string): string | undefined {
    const raw = css.match(new RegExp(`--color-${escapeRegExp(name)}:\\s*([^;]+);`))?.[1].trim();
    if (!raw) return undefined;
    const alias = raw.match(/^var\(--color-([\w.-]+)\)/);
    return (alias ? themeColour(alias[1]) : raw.replace(/\s*\/\*.*$/, '')).toUpperCase();
}

const KEYWORDS: Record<string, string> = { white: '#FFFFFF', transparent: 'transparent' };
const COLOUR_UTILITY = /^(?:[\w-]+:)*(text|bg|border(?:-[trblxy])?|ring|fill|stroke|decoration|outline|divide|from|to|via|caret|accent)-(.+?)(?:\/(\d+))?$/;

/** Every colour utility a rendered tree carries, resolved to the hex the stylesheet gives it. */
function resolvedColours(root: HTMLElement): Record<string, string> {
    const out: Record<string, string> = {};
    for (const element of [root, ...Array.from(root.querySelectorAll('*'))]) {
        for (const cls of (element.getAttribute('class') ?? '').split(/\s+/)) {
            const match = COLOUR_UTILITY.exec(cls);
            if (!match) continue;
            const [, , name, opacity] = match;
            const hex = KEYWORDS[name] ?? (name.startsWith('[#') ? name.slice(1, -1).toUpperCase() : themeColour(name));
            // Not a colour (`text-sm`, `border-t`, `bg-[length:…]`): nothing to pin.
            if (!hex) continue;
            out[cls.replace(/^(?:[\w-]+:)*/, '')] = opacity ? `${hex}@${opacity}%` : hex;
        }
    }
    return out;
}

afterEach(cleanup);

describe('the Default respondent preset', () => {
    const preset = ThemeColors.find((theme) => theme.title === 'Default')!;

    it('keeps its four colours', () => {
        expect({ primary: preset.primary, secondary: preset.secondary, tertiary: preset.tertiary, accent: preset.accent }).toEqual({
            primary: '#101828',
            secondary: '#1649E2',
            tertiary: '#818CA0',
            accent: '#F5F7FB'
        });
    });

    it('resolves to the same ground, focus ring, button face and highlight colours', () => {
        // A theme without type, shape or highlight sets no variable and no attribute.
        expect(themeRootProps(preset)).toEqual({ style: {}, attributes: {} });
        const { container } = render(
            <ReduxProvider store={store}>
                <Provider>
                    <LayoutWrapper theme={preset} disabled showDesktopLayout>
                        <h1>Title</h1>
                    </LayoutWrapper>
                </Provider>
            </ReduxProvider>
        );
        const root = container.firstElementChild as HTMLElement;
        expect(root.style.backgroundColor).toBe('rgb(245, 247, 251)');
        expect(root.style.getPropertyValue('--focus-ring')).toBe('#1649E2');
        expect(JSON.stringify(formButtonStyle(preset.secondary, '8px')).toUpperCase()).toContain('#1649E2');
        // No highlight of its own: the notes and the focus ring stay on the secondary.
        expect(highlightColours(preset)).toBeNull();
    });

    it('is what a stored legacy theme and a form with no theme both render', () => {
        // Stored forms carry their colours inline (the keys added later are null or absent).
        const stored = { title: 'Default', primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB', radius: null, highlight: null };
        const { container } = render(
            <ReduxProvider store={store}>
                <Provider>
                    <LayoutWrapper theme={stored} disabled showDesktopLayout>
                        <h1>Title</h1>
                    </LayoutWrapper>
                </Provider>
            </ReduxProvider>
        );
        const root = container.firstElementChild as HTMLElement;
        expect(root.style.backgroundColor).toBe('rgb(245, 247, 251)');
        expect(root.style.getPropertyValue('--focus-ring')).toBe('#1649E2');
        expect(root.querySelector('[data-form-radius],[data-form-highlight]')).toBeNull();
    });
});

describe('the trust strip and the "Powered by" badge', () => {
    it('trust strip: every colour utility resolves to the value it has today', () => {
        const { container } = render(
            <Provider>
                <I18nProvider>
                    <TrustLayer ownerName="Stichting Voorbeeld" poweredBy defaultExpanded portalUrl="/stichting-voorbeeld/portal" settings={{ purpose: 'Planning the open day', retentionDays: 30 } as never} />
                </I18nProvider>
            </Provider>
        );
        // Open it, so the panel's classes are part of the tree too.
        const toggle = screen.queryByRole('button', { expanded: false });
        if (toggle) fireEvent.click(toggle);
        expect(resolvedColours(container)).toEqual({
            'bg-white': '#FFFFFF',
            'bg-white/90': '#FFFFFF@90%',
            'border-t-black-400': '#D0D5DD',
            'bg-black-400': '#D0D5DD',
            'text-black-600': '#667085',
            'text-black-700': '#344054',
            'text-black-800': '#27303F',
            'text-black-900': '#101828',
            'text-brand-500': '#123FC9',
            'text-brand-600': '#1035A8',
            'text-brand-700': '#0E2D8F',
            'text-white': '#FFFFFF',
            'bg-black-100': '#F5F7FB',
            'bg-black-900': '#101828',
            'border-black-300': '#EAECF0',
            'ring-brand-500': '#123FC9'
        });
    });

    it('"Powered by" badge: every colour utility resolves to the value it has today', () => {
        const { container } = render(
            <ReduxProvider store={store}>
                <PoweredBy />
            </ReduxProvider>
        );
        expect(resolvedColours(container)).toEqual({
            'bg-white': '#FFFFFF',
            'border-black-300': '#EAECF0',
            'text-black-600': '#667085'
        });
        // The brand-owner tooltip face sits in a literal, not a token.
        const source = readFileSync(resolve(__dirname, '../../../components/ui/powered-by.tsx'), 'utf8');
        expect(source).toContain("backgroundColor: '#27303F'");
    });

    it('the tokens those utilities read are the frozen app ramps', () => {
        expect(['black-100', 'black-300', 'black-400', 'black-600', 'black-700', 'black-800', 'black-900', 'brand-500', 'brand-600', 'brand-700'].map(themeColour)).toEqual([
            '#F5F7FB',
            '#EAECF0',
            '#D0D5DD',
            '#667085',
            '#344054',
            '#27303F',
            '#101828',
            '#123FC9',
            '#1035A8',
            '#0E2D8F'
        ]);
    });
});

describe('respondent routes', () => {
    const read = (path: string) => readFileSync(resolve(__dirname, '../../..', path), 'utf8');

    it('wear the respondent wrapper on the form domain and on a custom domain', () => {
        for (const layout of ['app/(user-portal)/(no-layout)/[workspace_name]/forms/[form_id]/layout.tsx', 'app/(custom-domain)/(no-layout)/forms/[form_id]/layout.tsx']) {
            expect(read(layout)).toMatch(/<RespondentTypeface>/);
        }
    });

    it('a form with no stored theme paints no colour of its own and sits on paper mist', () => {
        const { container } = render(
            <ReduxProvider store={store}>
                <Provider>
                    <LayoutWrapper disabled showDesktopLayout>
                        <h1>Title</h1>
                    </LayoutWrapper>
                </Provider>
            </ReduxProvider>
        );
        const root = container.firstElementChild as HTMLElement;
        // nothing inline: the page ground behind it is the document's, which on a respondent route is paper mist
        expect(root.style.backgroundColor).toBe('');
        expect(root.getAttribute('style') ?? '').not.toContain('--focus-ring');
        const ground = (source: string) => source.match(/html,\s*body \{([^}]*)\}/)?.[1] ?? '';
        // Whatever the app's own ground is, outside an app scope it resolves to `black-100` (#F5F7FB).
        expect(ground(css)).toMatch(/@apply[^;]*\bbg-black-100\b|var\(--app-canvas, var\(--color-black-100\)\)/);
        expect(themeColour('black-100')).toBe('#F5F7FB');
    });
});

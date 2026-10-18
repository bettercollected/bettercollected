import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { FormTheme, THEME_STYLES, ThemeColors } from '@app/constants/theme';
import { store } from '@app/store/store';
import { choiceRowStyle } from '@app/views/atoms/choice';
import { scaleCellStyle } from '@app/views/molecules/responder-form-fields/linear-rating';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { formButtonStyle, highlightColours, outlinedButtonInk, themeRootProps } from './theme-root';
import { contrast, styleTokens } from './theme-shared';

/**
 * A theme without type, shape or highlight sets no variable and no attribute,
 * and every value a component draws through `var(--form-…, <fallback>)` then
 * resolves to exactly what it drew before these keys existed. jsdom does not
 * compute var(), so `resolve` does it the way a browser does.
 */
function resolve(value: unknown, vars: Record<string, string>): unknown {
    if (typeof value !== 'string') return value;
    let out = value;
    for (;;) {
        const match = /var\((--[\w-]+)(?:,\s*([^()]*(?:\([^()]*\))?[^()]*))?\)/.exec(out);
        if (!match) return out;
        out = out.replace(match[0], vars[match[1]] ?? match[2]?.trim() ?? '');
    }
}

const STORED_WITHOUT_KEYS = (theme: FormTheme): FormTheme => ({ ...theme, titleFont: null, bodyFont: null, dataFont: null, titleWidth: null, radius: null, buttonStyle: null, highlight: null });

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

const themeRoot = (container: HTMLElement) => container.firstElementChild as HTMLElement;

describe('a theme without type, shape or highlight renders as before', () => {
    const themes = [...ThemeColors, ...ThemeColors.map(STORED_WITHOUT_KEYS), ...THEME_STYLES.map((style) => ({ ...ThemeColors[0], style }))];

    it.each(themes.map((theme, i) => [`${theme.title} #${i}`, theme]))('%s sets no variable and no attribute', (_name, theme) => {
        expect(themeRootProps(theme as FormTheme)).toEqual({ style: {}, attributes: {} });
        const { container } = wrap(
            <LayoutWrapper theme={theme as FormTheme} disabled showDesktopLayout>
                <h1>Title</h1>
            </LayoutWrapper>
        );
        const root = themeRoot(container);
        // The root's inline style is the one it always had: ground and focus colour.
        expect(root.getAttribute('style')).toBe(`background-color: ${hexToRgb((theme as FormTheme).accent)}; --focus-ring: ${(theme as FormTheme).secondary};`);
        expect(container.querySelector('[data-form-title-font],[data-form-body-font],[data-form-data-font],[data-form-title-width],[data-form-radius],[data-form-buttons],[data-form-highlight]')).toBeNull();
    });

    it.each(themes.map((theme, i) => [`${theme.title} #${i}`, theme]))('%s: fields, options and buttons resolve to their old values', (_name, theme) => {
        const t = theme as FormTheme;
        const vars = themeRootProps(t).style as Record<string, string>;
        const tokens = styleTokens(t.style);
        expect(resolve(tokens.fieldRadius, vars)).toBe(tokens.inputRadius);
        expect(resolve(tokens.cardRadius, vars)).toBe(tokens.inputRadius);
        for (const selected of [false, true]) {
            const row = choiceRowStyle(t, selected).style as Record<string, unknown>;
            const solid = tokens.solidSelection && selected;
            const before: Record<string, unknown> = tokens.ruledChoices
                ? {}
                : {
                      '--choice-edge-hover': selected ? t.secondary : t.primary,
                      background: solid ? t.secondary : selected ? t.secondary + '1A' : '',
                      '--choice-edge': selected ? t.secondary : t.tertiary,
                      color: solid ? '#ffffff' : t.primary,
                      borderRadius: tokens.inputRadius
                  };
            before['--choice-indicator-hover'] = selected ? (solid ? '#ffffff' : t.secondary) : t.primary;
            for (const [key, value] of Object.entries(before)) expect(resolve(row[key], vars)).toBe(value);
        }
        const button = formButtonStyle(t.secondary, '8px') as Record<string, unknown>;
        expect(Object.fromEntries(Object.entries(button).map(([k, v]) => [k, resolve(v, vars)]))).toEqual({ background: t.secondary, color: '#FFFFFF', boxShadow: 'none', borderRadius: '8px' });
    });
});

describe('type and shape', () => {
    const kantlijnLike: FormTheme = {
        title: 'Mine',
        primary: '#16261F',
        secondary: '#1E4D3B',
        tertiary: '#7D8C84',
        accent: '#FFFFFF',
        titleFont: 'besley',
        bodyFont: 'atkinson-next',
        dataFont: 'atkinson-mono',
        radius: 'soft',
        buttonStyle: 'filled',
        highlight: '#A3305A'
    };

    it('sets the faces, corners and highlight at the theme root, for the canvas and the page alike', () => {
        const { container } = wrap(
            <LayoutWrapper theme={kantlijnLike} disabled showDesktopLayout>
                <h1>Title</h1>
            </LayoutWrapper>
        );
        const root = themeRoot(container);
        expect(root.dataset).toMatchObject({ formTitleFont: 'besley', formBodyFont: 'atkinson-next', formDataFont: 'atkinson-mono', formRadius: 'soft', formButtons: 'filled', formHighlight: '' });
        expect(root.style.getPropertyValue('--form-font-title')).toContain('Besley');
        expect(root.style.getPropertyValue('--font-form')).toContain('Atkinson Hyperlegible Next');
        expect(root.style.getPropertyValue('--form-radius-field')).toBe('6px');
        // Rose reads on white (6.7:1): it is the focus ring and the chosen edge.
        expect(root.style.getPropertyValue('--focus-ring')).toBe('#A3305A');
        expect(root.style.getPropertyValue('--form-highlight-edge')).toBe('#A3305A');
    });

    it('sets an expanded title width and pill buttons', () => {
        const props = themeRootProps({ ...ThemeColors[0], titleFont: 'archivo', titleWidth: 'expanded', radius: 'sharp', buttonStyle: 'pill' });
        expect(props.attributes).toMatchObject({ 'data-form-title-width': 'expanded', 'data-form-radius': 'sharp', 'data-form-buttons': 'pill' });
        expect(props.style).toMatchObject({ '--form-radius-field': '0px', '--form-radius-card': '0px', '--form-radius-button': '9999px' });
    });

    it('ignores values that are not on the lists', () => {
        expect(themeRootProps({ ...ThemeColors[0], titleFont: 'comic' as any, radius: 'huge' as any, buttonStyle: 'ghost' as any, highlight: 'red' })).toEqual({ style: {}, attributes: {} });
    });

    it.each(ThemeColors.map((theme) => [theme.title, theme]))('%s: outlined buttons keep 4.5:1 text and 3:1 edges on the page', (_title, theme) => {
        const { style } = themeRootProps({ ...theme, buttonStyle: 'outlined' }) as { style: Record<string, string> };
        const ground = style['--form-button-bg'];
        const ink = style['--form-button-fg'];
        expect(ground).toBe(theme.accent);
        expect(contrast(ink, ground)).toBeGreaterThanOrEqual(4.5);
        expect(style['--form-button-edge']).toBe(`inset 0 0 0 2px ${ink}`);
        expect(outlinedButtonInk(theme)).toBe(ink);
    });

    it('keeps a light highlight off text and edges, and fills the chosen option with it instead', () => {
        const lemon = highlightColours({ ...ThemeColors[0], primary: '#0F3936', accent: '#FFFFFF', highlight: '#FFD84D' })!;
        expect(lemon).toMatchObject({ edge: '#0F3936', text: '#0F3936', fill: '#FFD84D', fillInk: '#0F3936', focus: undefined });
        expect(contrast(lemon.fillInk, lemon.fill)).toBeGreaterThanOrEqual(4.5);
        const rose = highlightColours({ ...ThemeColors[0], accent: '#FFFFFF', highlight: '#A3305A' })!;
        expect(rose).toMatchObject({ edge: '#A3305A', text: '#A3305A', fill: '#A3305A1A', solidInk: '#FFFFFF', focus: '#A3305A' });
        expect(highlightColours(ThemeColors[0])).toBeNull();
    });

    it.each(ThemeColors.map((theme) => [theme.title, theme]))('%s: every highlight stays legible where it is used', (_title, theme) => {
        for (const highlight of ['#FFD84D', '#A3305A', '#2B2FD1', '#FFFFFF', '#000000', '#7F7F7F']) {
            const colours = highlightColours({ ...theme, highlight })!;
            expect(contrast(colours.edge, theme.accent)).toBeGreaterThanOrEqual(contrast(theme.primary, theme.accent) >= 3 ? 3 : 0);
            expect(contrast(colours.text, theme.accent)).toBeGreaterThanOrEqual(Math.min(4.5, contrast(theme.primary, theme.accent)));
            if (colours.focus) expect(contrast(colours.focus, theme.accent)).toBeGreaterThanOrEqual(3);
            expect(contrast(colours.solidInk, colours.solid)).toBeGreaterThanOrEqual(Math.min(4.5, Math.max(contrast('#FFFFFF', highlight), contrast(theme.primary, highlight))));
        }
    });
});

describe('the chosen option and rating number keep a visible edge with any highlight', () => {
    const highlights = ['#FFD84D', '#A3305A', '#2B2FD1', '#FFFFFF'];
    const cases = ThemeColors.flatMap((preset) => THEME_STYLES.flatMap((style) => highlights.map((highlight) => ({ ...preset, style, highlight }) as FormTheme)));

    it.each(cases.map((theme) => [`${theme.title} ${theme.style} ${theme.highlight}`, theme]))('%s', (_name, theme) => {
        const t = theme as FormTheme;
        const vars = themeRootProps(t).style as Record<string, string>;
        const tokens = styleTokens(t.style);
        // The rating's chosen number: filled with the highlight, its edge at
        // 3:1 on the page (the ink for a light highlight), as option cards.
        const cell = scaleCellStyle(t, true, tokens.cardRadius) as Record<string, unknown>;
        const edge = resolve(cell['--scale-edge'], vars) as string;
        expect(edge).toBe(highlightColours(t)!.edge);
        if (contrast(t.primary, t.accent) >= 3) expect(contrast(edge, t.accent)).toBeGreaterThanOrEqual(3);
        expect(resolve(cell['--scale-edge-hover'], vars)).toBe(edge);
        expect(resolve(cell.background, vars)).toBe(t.highlight);
        // A chosen option card (tinted, or solid in the studio style) has the same edge.
        if (!tokens.ruledChoices) expect(resolve((choiceRowStyle(t, true).style as Record<string, unknown>)['--choice-edge'], vars)).toBe(edge);
    });

    it('draws the rating as before without a highlight', () => {
        const t = ThemeColors[0];
        const cell = scaleCellStyle(t, true, '6px') as Record<string, unknown>;
        const vars = themeRootProps(t).style as Record<string, string>;
        expect([cell['--scale-edge'], cell['--scale-edge-hover'], cell.background, cell.color].map((v) => resolve(v, vars))).toEqual([t.secondary, t.secondary, t.secondary, '#ffffff']);
    });
});

function hexToRgb(hex: string): string {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    return `rgb(${r}, ${g}, ${b})`;
}

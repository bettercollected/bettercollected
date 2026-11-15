import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { store } from '@app/store/store';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { ThemeArtworkBand } from './theme-artwork';
import { highlightColours, themeRootProps } from './theme-root';
import { themeBackgroundStyle } from './theme-shared';

/**
 * Published forms keep the look they have. A form wears its stored theme (the
 * colours are saved inline); a form with no theme renders the Default preset.
 * New presets are added next to the old ones and never edit them, so what a
 * form with no theme, with the Default preset or with a stored older theme
 * draws is pinned here: the variables, the page ground and the markup of the
 * page wrapper. A change that moves any of them fails before it can ship.
 */

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

// A form stored before type, shape and highlight existed: keys null or absent.
const STORED_OCEAN: FormTheme = { title: 'Ocean', primary: '#111827', secondary: '#1D4ED8', tertiary: '#2563EB', accent: '#DBEAFE', style: undefined, titleFont: null, bodyFont: null, dataFont: null, titleWidth: null, radius: null, buttonStyle: null, highlight: null, selection: null };
// An older form that carries its own gradient ground.
const STORED_GRADIENT: FormTheme = { title: 'Custom', primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB', background: { type: 'gradient', gradientFrom: '#F5F7FB', gradientTo: '#DBEAFE', gradientAngle: 135 } };
const DEFAULT = ThemeColors.find((theme) => theme.title === 'Default')!;

const CASES: Array<[string, FormTheme | undefined]> = [
    ['no theme', undefined],
    ['Default', DEFAULT],
    ['stored Ocean', STORED_OCEAN],
    ['stored gradient', STORED_GRADIENT]
];

describe('the Default preset', () => {
    it('is the Sireto palette', () => {
        expect(DEFAULT).toEqual({ title: 'Default', primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB' });
    });
});

describe.each(CASES)('a form with %s', (_name, theme) => {
    it('sets no theme variable and no attribute, and no highlight', () => {
        expect(themeRootProps(theme)).toEqual({ style: {}, attributes: {} });
        expect(highlightColours(theme)).toBeNull();
    });

    it('has no artwork band', () => {
        expect(ThemeArtworkBand({ theme })).toBeNull();
    });

    it('draws the same page ground', () => {
        const ground = themeBackgroundStyle(theme);
        expect(ground).toMatchSnapshot();
        expect(JSON.stringify(ground)).not.toContain('svg');
    });

    it('wraps the page in the same markup', () => {
        const { container } = wrap(
            <LayoutWrapper theme={theme} disabled showDesktopLayout>
                <h1>Title</h1>
            </LayoutWrapper>
        );
        expect(container.innerHTML).not.toContain('data:image/svg');
        expect(container.innerHTML).toMatchSnapshot();
    });
});

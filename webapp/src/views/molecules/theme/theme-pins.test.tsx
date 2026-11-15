import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { FormTheme, ThemeColors, welcomeLayoutAfterPreset } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';
import { store } from '@app/store/store';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { ThemeArtworkBand, greetingCover } from './theme-artwork';
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

/**
 * A form with the stored Kantlijn theme (the marble artwork, a complete look):
 * the picture half of a welcome or ending page, the ending's band, the cover of
 * a welcome page set beside the artwork and the welcome layout a preset change
 * gives are the code a new artwork touched, so what they draw for marble is
 * pinned too. Written against origin/develop's components and green there.
 */
describe('a form with the stored Kantlijn theme (marble)', () => {
    const KANTLIJN = ThemeColors.find((theme) => theme.title === 'Kantlijn')!;
    const OCEAN = ThemeColors.find((theme) => theme.title === 'Ocean')!;
    const RASTER = ThemeColors.find((theme) => theme.title === 'Raster')!;
    const page = (props: Partial<React.ComponentProps<typeof LayoutWrapper>>) =>
        wrap(
            <LayoutWrapper theme={KANTLIJN} disabled showDesktopLayout {...props}>
                <h1>Title</h1>
            </LayoutWrapper>
        ).container.innerHTML;

    it('sets the same variables and page ground', () => {
        expect(themeRootProps(KANTLIJN)).toMatchSnapshot('root');
        expect(highlightColours(KANTLIJN)).toMatchSnapshot('highlight');
        expect(themeBackgroundStyle(KANTLIJN)).toMatchSnapshot('ground');
        expect(themeBackgroundStyle(KANTLIJN, { compact: true })).toMatchSnapshot('compact ground');
        expect(themeBackgroundStyle(KANTLIJN, { leftAligned: true })).toMatchSnapshot('left aligned ground');
    });

    it('draws the same band along the top of an ending', () => {
        expect(wrap(<ThemeArtworkBand theme={KANTLIJN} />).container.innerHTML).toMatchSnapshot();
        expect(page({ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, artworkBand: true })).toMatchSnapshot('ending with the band');
    });

    it('fills the picture half of a page set beside an image with the artwork', () => {
        expect(page({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT })).toMatchSnapshot('picture half right');
        expect(page({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT })).toMatchSnapshot('picture half left');
        // a page with an image of its own keeps it
        expect(page({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, imageUrl: 'https://images.unsplash.com/photo-1' })).not.toContain('data-testid="theme-artwork"');
    });

    it('makes the same cover for a welcome page set beside the artwork', () => {
        expect(greetingCover(KANTLIJN, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toMatchSnapshot('cover');
        expect(greetingCover(KANTLIJN, FormSlideLayout.TWO_COLUMN_IMAGE_LEFT)).toMatchSnapshot('cover left');
        expect(greetingCover(KANTLIJN, FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND)).toBeNull();
        expect(greetingCover(KANTLIJN, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, 'https://images.unsplash.com/photo-1')).toBeNull();
        expect(greetingCover(OCEAN, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toBeNull();
    });

    it('gives the same welcome layout after a preset change', () => {
        const beside = { layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT };
        expect(welcomeLayoutAfterPreset(beside, KANTLIJN, OCEAN)).toBe(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
        expect(welcomeLayoutAfterPreset({ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND }, OCEAN, KANTLIJN)).toBe(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT);
        expect(welcomeLayoutAfterPreset(beside, OCEAN, KANTLIJN)).toBeUndefined();
        expect(welcomeLayoutAfterPreset(beside, KANTLIJN, RASTER)).toBe(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN);
        expect(welcomeLayoutAfterPreset({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, imageUrl: 'https://images.unsplash.com/photo-1' }, KANTLIJN, OCEAN)).toBeUndefined();
        expect(welcomeLayoutAfterPreset(beside, OCEAN, ThemeColors[0])).toBeUndefined();
        expect(welcomeLayoutAfterPreset(null, OCEAN, KANTLIJN)).toBeUndefined();
    });
});

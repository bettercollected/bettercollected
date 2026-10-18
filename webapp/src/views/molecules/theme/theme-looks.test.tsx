// The complete-look presets (Kantlijn, Raster): every key set, valid under
// the shared checks, AA wherever their colours meet, their background
// treatments, the welcome layout they set, the marble artwork and the cover.
import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { FormTheme, PRESET_WELCOME_LAYOUTS, THEME_TYPE_SHAPE_KEYS, ThemeColors, findPreset, themeProblems, welcomeLayoutAfterPreset } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { AA_NON_TEXT, AA_TEXT } from '@app/utils/color-contrast';
import { themeContrastChecks } from '@app/utils/theme-contrast';
import { SubmissionReceipt } from '@app/views/organism/form/thankyou-page';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { greetingCover, themeArtwork } from './theme-artwork';
import { highlightColours, outlinedButtonInk, themeRootProps } from './theme-root';
import { contrast, mixHex, themeBackgroundStyle } from './theme-shared';

const KANTLIJN = findPreset('Kantlijn')!;
const RASTER = findPreset('Raster')!;
const LOOKS = [KANTLIJN, RASTER];

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

describe.each(LOOKS.map((theme) => [theme.title, theme] as const))('the %s preset', (_title, theme) => {
    it('sets every type and shape key, its style and its background, so nothing of the previous look stays', () => {
        for (const key of THEME_TYPE_SHAPE_KEYS) expect(theme[key]).toBeTruthy();
        expect(theme.style).toBeTruthy();
        expect(theme.background?.type).toBe('pattern');
    });

    it('passes the checks every writer applies', () => {
        expect(themeProblems(theme)).toEqual([]);
    });

    it.each(themeContrastChecks(theme).map((check) => [check.label, check] as const))('meets AA: %s', (_label, check) => {
        expect(check.ratio).toBeGreaterThanOrEqual(check.minimum);
    });

    it('keeps text, controls and focus at AA on the white sheet the questions sit on', () => {
        expect(contrast(theme.primary, '#FFFFFF')).toBeGreaterThanOrEqual(AA_TEXT);
        expect(contrast(theme.tertiary, '#FFFFFF')).toBeGreaterThanOrEqual(AA_NON_TEXT);
        const colours = highlightColours(theme);
        for (const ground of [theme.accent, '#FFFFFF']) {
            const focus = colours?.focus ?? theme.secondary;
            expect(contrast(focus, ground)).toBeGreaterThanOrEqual(AA_NON_TEXT);
            if (colours?.text) expect(contrast(colours.text, ground)).toBeGreaterThanOrEqual(AA_TEXT);
            if (colours) expect(contrast(colours.edge, ground)).toBeGreaterThanOrEqual(AA_NON_TEXT);
            // the chosen option's text on its 10% tint
            expect(contrast(theme.primary, mixHex(colours?.solid ?? theme.secondary, ground, 26 / 255))).toBeGreaterThanOrEqual(AA_TEXT);
        }
        if (colours) expect(contrast(colours.solidInk, colours.solid)).toBeGreaterThanOrEqual(AA_TEXT);
    });

    it('draws buttons whose text and edges pass AA, at rest and on hover', () => {
        const { style } = themeRootProps(theme) as { style: Record<string, string> };
        if (theme.buttonStyle === 'outlined') {
            expect(contrast(style['--form-button-fg'], style['--form-button-bg'])).toBeGreaterThanOrEqual(AA_TEXT);
            expect(contrast(style['--form-button-hover-fg'], style['--form-button-hover-bg'])).toBeGreaterThanOrEqual(AA_TEXT);
            expect(outlinedButtonInk(theme)).toBe(style['--form-button-fg']);
        } else {
            expect(contrast('#FFFFFF', theme.secondary)).toBeGreaterThanOrEqual(AA_TEXT);
        }
    });

    it('names the welcome layout it is made for', () => {
        expect(PRESET_WELCOME_LAYOUTS[theme.title]).toBeTruthy();
    });
});

describe('Kantlijn', () => {
    it('keeps the chosen answer in the cloth and the rose for notes, the margin rule and focus', () => {
        const colours = highlightColours(KANTLIJN)!;
        expect(colours).toMatchObject({ edge: '#1E4D3B', solid: '#1E4D3B', text: '#A3305A', rule: '#A3305A', focus: '#A3305A' });
    });

    it('sets its cover beside the marble at AA, with the button turned to the page colour', () => {
        const cover = greetingCover(KANTLIJN, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, '')!;
        expect(cover.theme.accent).toBe('#1E4D3B');
        expect(cover.theme.primary).toBe('#F8EEEC');
        expect(contrast(cover.theme.primary, cover.theme.accent)).toBeGreaterThanOrEqual(AA_TEXT);
        expect(cover.style).toMatchObject({ '--form-button-bg': '#F8EEEC', '--form-button-fg': '#1E4D3B' });
        // focus ring on the cover: the cover's secondary (blush on cloth)
        expect(contrast(cover.theme.secondary, cover.theme.accent)).toBeGreaterThanOrEqual(AA_NON_TEXT);
    });

    it('has no cover without its artwork, with an image of the page own, centred, private or in the Leaflet style', () => {
        expect(greetingCover(KANTLIJN, FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND)).toBeNull();
        expect(greetingCover(KANTLIJN, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, 'https://images.unsplash.com/photo-1')).toBeNull();
        expect(greetingCover(KANTLIJN, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, '', { privateForm: true })).toBeNull();
        expect(greetingCover({ ...KANTLIJN, style: 'leaflet' }, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toBeNull();
        expect(greetingCover({ ...KANTLIJN, background: undefined }, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toBeNull();
        // the page and button colours must read on each other
        expect(greetingCover({ ...KANTLIJN, secondary: '#E8DCDA' }, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toBeNull();
    });

    it('sets questions on a white sheet right of a rose margin rule', () => {
        const ground = themeBackgroundStyle(KANTLIJN);
        expect(ground.backgroundColor).toBe('#F8EEEC');
        expect(String(ground.backgroundImage)).toContain('#A3305A calc(50% - 392px)');
        expect(String(ground.backgroundImage)).toContain('#FFFFFF calc(calc(50% - 392px) + 1px)');
        // A left-aligned column has no margin: all sheet.
        expect(String(themeBackgroundStyle(KANTLIJN, { leftAligned: true }).backgroundImage)).toContain('-2px');
    });

    it('shows the marble in an empty picture half, from the app itself, decoratively', () => {
        const { container } = wrap(
            <LayoutWrapper theme={KANTLIJN} layout={FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT} disabled>
                <h1>Title</h1>
            </LayoutWrapper>
        );
        const art = container.querySelector('[data-testid="theme-artwork"]')!;
        expect(art).not.toBeNull();
        expect(art.getAttribute('aria-hidden')).toBe('true');
        expect(art.querySelector('img')!.getAttribute('alt')).toBe('');
        const sources = Array.from(art.querySelectorAll('source')).map((source) => source.getAttribute('type'));
        expect(sources).toEqual(['image/avif', 'image/webp', 'image/avif']);
        for (const url of [...Array.from(art.querySelectorAll('source')).map((source) => source.getAttribute('srcset') ?? ''), art.querySelector('img')!.getAttribute('src') ?? '']) {
            expect(url).not.toMatch(/https?:\/\//);
            expect(url).toMatch(/marble-(panel|strip)/);
        }
        // the placeholder is inline, not a request
        expect((art as HTMLElement).style.backgroundImage).toContain('data:image/webp;base64,');
    });

    it('keeps the marble beside its cover', () => {
        const cover = greetingCover(KANTLIJN, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)!;
        const { container } = wrap(
            <LayoutWrapper theme={cover.theme} artworkTheme={KANTLIJN} style={cover.style} layout={FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT} disabled>
                <h1>Title</h1>
            </LayoutWrapper>
        );
        expect(container.querySelector('[data-testid="theme-artwork"]')).not.toBeNull();
    });

    it('runs the marble as a band along an ending without a picture half', () => {
        const { container } = wrap(
            <LayoutWrapper theme={KANTLIJN} layout={FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND} artworkBand disabled>
                <h1>Thank you</h1>
            </LayoutWrapper>
        );
        expect(container.querySelector('[data-testid="theme-artwork-band"]')).not.toBeNull();
        expect(container.querySelector('[data-testid="theme-artwork"]')).toBeNull();
    });
});

describe('Raster', () => {
    it('draws its grid as faint hairlines between the page margins, never as information', () => {
        const ground = themeBackgroundStyle(RASTER);
        expect(ground.backgroundImage).toBe('linear-gradient(90deg, #6D708333 1px, transparent 1px)');
        expect(ground.backgroundSize).toContain('var(--form-grid-columns, 12)');
        // 20% of the edge colour on white: about 1.3:1, ink stays at 19:1 over it
        const line = mixHex('#6D7083', '#FFFFFF', 0.2);
        expect(contrast(line, '#FFFFFF')).toBeLessThan(1.5);
        expect(contrast(RASTER.primary, line)).toBeGreaterThanOrEqual(AA_TEXT);
    });

    it('fills options at rest with the page colour so the grid never runs through an answer', () => {
        const { attributes, style } = themeRootProps(RASTER) as { attributes: Record<string, string>; style: Record<string, string> };
        expect(attributes['data-form-ground']).toBe('columns');
        expect(style['--form-ground-fill']).toBe('#FFFFFF');
        expect(themeRootProps(KANTLIJN).attributes['data-form-ground']).toBeUndefined();
    });

    it('fills the chosen answer with its ultramarine (the studio style), white on it', () => {
        expect(highlightColours(RASTER)).toBeNull();
        expect(contrast('#FFFFFF', RASTER.secondary)).toBeGreaterThanOrEqual(AA_TEXT);
    });

    it('has no artwork', () => {
        expect(themeArtwork(RASTER)).toBeNull();
    });

    it('sets the submission number as the headline, in its data face and ultramarine', () => {
        store.dispatch(setForm({ formId: 'f1', title: 'Doe mee', theme: RASTER, fields: [] }));
        const { container } = wrap(<SubmissionReceipt responderId="6ad4aac46a486750fb81c55b" submissionUrl="" onCopy={() => {}} edge="#D0D5DD" />);
        const number = container.querySelector('[data-headline]') as HTMLElement;
        expect(number).not.toBeNull();
        expect(number.className).toContain('sm:text-[40px]');
        expect(number.style.color).toBe('rgb(43, 47, 209)');
        // Kantlijn (classic style) keeps today's receipt.
        store.dispatch(setForm({ formId: 'f1', title: 'Doe mee', theme: KANTLIJN, fields: [] }));
        const other = wrap(<SubmissionReceipt responderId="6ad4aac46a486750fb81c55b" submissionUrl="" onCopy={() => {}} edge="#D0D5DD" />);
        expect(other.container.querySelector('[data-headline]')).toBeNull();
    });
});

describe('the welcome layout a preset sets', () => {
    const OCEAN = findPreset('Ocean')!;

    it('takes the preset layout when the welcome page has no image of its own', () => {
        expect(welcomeLayoutAfterPreset({}, OCEAN, KANTLIJN)).toBe(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT);
        expect(welcomeLayoutAfterPreset({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT }, KANTLIJN, RASTER)).toBe(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN);
        expect(welcomeLayoutAfterPreset({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT }, KANTLIJN, KANTLIJN)).toBeUndefined();
    });

    it('keeps a welcome page with an image of its own', () => {
        expect(welcomeLayoutAfterPreset({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT, imageUrl: 'https://images.unsplash.com/photo-1' }, OCEAN, KANTLIJN)).toBeUndefined();
    });

    it('returns a page left beside an artwork the new theme lacks to the default, and leaves the rest', () => {
        expect(welcomeLayoutAfterPreset({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT }, KANTLIJN, OCEAN)).toBe(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
        expect(welcomeLayoutAfterPreset({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT }, OCEAN, findPreset('Mint')!)).toBeUndefined();
        expect(welcomeLayoutAfterPreset({ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN }, RASTER, OCEAN)).toBeUndefined();
        expect(welcomeLayoutAfterPreset(null, OCEAN, KANTLIJN)).toBeUndefined();
    });
});

describe('the colour presets stay as they were', () => {
    it.each(ThemeColors.filter((theme) => !LOOKS.includes(theme)).map((theme) => [theme.title, theme] as const))('%s sets no type, shape, selection or background', (_title, theme) => {
        const t = theme as FormTheme;
        for (const key of THEME_TYPE_SHAPE_KEYS) expect(t[key]).toBeUndefined();
        expect(t.highlight).toBeUndefined();
        expect(t.selection).toBeUndefined();
        expect(t.background).toBeUndefined();
        expect(themeArtwork(t)).toBeNull();
        expect(greetingCover(t, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toBeNull();
    });

    it('validates the selection and artwork, word for word with the backend', () => {
        expect(themeProblems({ ...KANTLIJN, selection: 'cloth', background: { type: 'color', artwork: 'photo' as any } })).toEqual(['theme.selection must be a 6-digit hex colour, e.g. #1E4D3B.', 'theme.background.artwork must be one of: marble.']);
        // stored patterns are not held to the list
        expect(themeProblems({ ...KANTLIJN, background: { type: 'pattern', pattern: 'waves' as any } })).toEqual([]);
    });
});

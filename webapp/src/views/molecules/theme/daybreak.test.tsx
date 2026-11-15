import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { FormTheme, GATED_PRESETS, ThemeColors, findPreset, isPresetOffered, offeredPresets, welcomeLayoutAfterPreset } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';
import { store } from '@app/store/store';
import { contrast } from '@app/utils/color-contrast';
import { applyOps } from '@app/lib/form-ops';
import { ChoiceContent } from '@app/views/atoms/choice';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { DAYBREAK_RULE, DAYBREAK_SUN, DaybreakSunrise, daybreakCornerStyle, daybreakRule } from './daybreak-art';
import { ThemeArtworkBand, greetingCover, themeArtwork, themePictureArtwork } from './theme-artwork';
import { themeRootProps } from './theme-root';
import { themeBackgroundStyle } from './theme-shared';

const DAYBREAK = findPreset('Daybreak')!;
const DEFAULT = findPreset('Default')!;
const KANTLIJN = findPreset('Kantlijn')!;

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

describe('the Daybreak preset', () => {
    it('keeps the action blue of the Default preset and adds only colours, the classic style and its scene', () => {
        expect(DAYBREAK.secondary).toBe(DEFAULT.secondary);
        expect(DAYBREAK.style).toBe('classic');
        expect(DAYBREAK.background).toEqual({ type: 'color', artwork: 'daybreak' });
        for (const key of ['titleFont', 'bodyFont', 'dataFont', 'titleWidth', 'radius', 'buttonStyle', 'highlight', 'selection', 'inputText'] as const) expect(DAYBREAK[key]).toBeUndefined();
    });

    // The pairs the form draws (backend tests/app/services/test_daybreak_preset.py checks the same).
    const page = DAYBREAK.accent;
    it.each([
        ['questions and text on the page', DAYBREAK.primary, page, 4.5],
        ['answers typed in the white input boxes', DAYBREAK.primary, '#FFFFFF', 4.5],
        ['button text on the action colour', '#FFFFFF', DAYBREAK.secondary, 4.5],
        ['action colour on the page', DAYBREAK.secondary, page, 3],
        ['input borders on the page', DAYBREAK.tertiary, page, 3],
        ['input borders on white', DAYBREAK.tertiary, '#FFFFFF', 3],
        ['the why-we-ask rule on the page', DAYBREAK_RULE, page, 3],
        ['ink on the sun', DAYBREAK.primary, DAYBREAK_SUN, 4.5]
    ])('%s reads', (_name, foreground, background, minimum) => {
        expect(contrast(foreground, background)).toBeGreaterThanOrEqual(minimum);
    });

    it('is offered only when the server says so, and a form that wears it keeps it either way', () => {
        expect(GATED_PRESETS).toEqual(['Daybreak']);
        expect(isPresetOffered('Daybreak', [])).toBe(false);
        expect(isPresetOffered('Daybreak', undefined)).toBe(false);
        expect(isPresetOffered('Daybreak', ['Daybreak'])).toBe(true);
        expect(isPresetOffered('Ocean', [])).toBe(true);
        expect(offeredPresets([]).map((p) => p.title)).toEqual(ThemeColors.map((p) => p.title).filter((t) => t !== 'Daybreak'));
        expect(offeredPresets(['Daybreak'])).toHaveLength(ThemeColors.length);
        // stored values never depend on the switch
        expect(themeRootProps(DAYBREAK).style).toEqual({ '--form-highlight-rule': DAYBREAK_RULE });
        expect(themeBackgroundStyle(DAYBREAK).backgroundImage).toContain('data:image/svg+xml');
    });

    it('is refused by the edit engine while off, as an unknown preset is, and applied while on', () => {
        const doc = { title: 'F', fields: [] } as any;
        const off = applyOps(doc, [{ op: 'set_theme_preset', name: 'Daybreak' }] as any, { offeredGatedPresets: [] });
        expect(off.results[0].ok).toBe(false);
        expect(off.results[0].message).toContain("There is no theme preset named 'Daybreak'");
        expect(off.results[0].message).not.toMatch(/Pick one of:.*Daybreak/);
        const on = applyOps(doc, [{ op: 'set_theme_preset', name: 'daybreak' }] as any, { offeredGatedPresets: ['Daybreak'] });
        expect(on.results[0].ok).toBe(true);
        expect((on.doc as any).theme.background.artwork).toBe('daybreak');
        // no list given: everything is offered (the corpus, the server's own run)
        expect(applyOps(doc, [{ op: 'set_theme_preset', name: 'Daybreak' }] as any).results[0].ok).toBe(true);
    });
});

describe('the corner sun', () => {
    it('is the page ground of a Daybreak form only, behind the questions, scaled with the page', () => {
        const ground = themeBackgroundStyle(DAYBREAK);
        expect(ground.backgroundColor).toBe('#F3F6FF');
        expect(ground.backgroundPosition).toBe('top right');
        expect(ground.backgroundRepeat).toBe('no-repeat');
        expect(ground.backgroundSize).toBe('clamp(130px, 18vw, 260px) auto');
        const image = decodeURIComponent(String(ground.backgroundImage));
        expect(image).toContain('<svg');
        expect(image).not.toMatch(/https?:\/\/(?!www\.w3\.org)/); // first-party: nothing fetched
        expect(daybreakCornerStyle(true).backgroundSize).toBe('48px auto');
        expect(themeBackgroundStyle(DEFAULT).backgroundImage).toBeUndefined();
        expect(themeBackgroundStyle(KANTLIJN).backgroundImage).not.toContain('svg');
    });

    it('is on the page wrapper of a Daybreak form and not of the Default one', () => {
        const html = (theme: FormTheme) => wrap(<LayoutWrapper theme={theme} disabled showDesktopLayout><h1>Title</h1></LayoutWrapper>).container.innerHTML;
        expect(html(DAYBREAK)).toContain('data:image/svg+xml');
        expect(html(DEFAULT)).not.toContain('data:image/svg+xml');
    });

    it('leaves the focus ring and the chosen answer in the action colour and colours only the rule', () => {
        const root = themeRootProps(DAYBREAK);
        expect(root.attributes).toEqual({});
        expect(Object.keys(root.style)).toEqual(['--form-highlight-rule']);
        expect(daybreakRule(DAYBREAK)).toBe(DAYBREAK_RULE);
        // a page the sun does not read on gets the ink instead
        expect(daybreakRule({ ...DAYBREAK, accent: '#B07400' })).toBe(DAYBREAK.primary);
        // a form's own highlight wins
        expect(themeRootProps({ ...DAYBREAK, highlight: '#1035A8' }).style['--form-highlight-rule' as keyof React.CSSProperties]).not.toBe(DAYBREAK_RULE);
    });
});

describe('the chosen answer', () => {
    const chosen = (theme: FormTheme) => wrap(<ChoiceContent kind="radio" selected theme={theme}>Every month</ChoiceContent>).container;
    it('ends in a check on a Daybreak form (shape as well as colour), and only there', () => {
        expect(chosen(DAYBREAK).querySelector('[data-choice-check]')).not.toBeNull();
        expect(chosen(DEFAULT).querySelector('[data-choice-check]')).toBeNull();
        expect(chosen(KANTLIJN).querySelector('[data-choice-check]')).toBeNull();
    });
});

describe('the sunrise on the ending', () => {
    it('is the ending band of a Daybreak form: hills in front of a sun, a check drawn inside it, decorative', () => {
        const { container } = wrap(<ThemeArtworkBand theme={DAYBREAK} />);
        const band = container.querySelector('[data-testid="daybreak-sunrise"]')!;
        expect(band).not.toBeNull();
        expect(band.getAttribute('aria-hidden')).toBe('true');
        const svg = band.querySelector('svg')!;
        const order = Array.from(svg.children).map((el) => el.tagName + (el.getAttribute('class') ? `.${el.getAttribute('class')}` : ''));
        // the sun (with its check) is drawn first, so the two hills cover its foot
        expect(order.slice(0, 3)).toEqual(['g.bc-daybreak-rise', 'path', 'path']);
        expect(svg.querySelectorAll('path.bc-daybreak-check')).toHaveLength(1);
        expect(band.innerHTML).not.toMatch(/<(image|img|script|foreignObject)|href=/i);
    });

    it('plays once over about a second with ease-out, draws the check after it, and has no motion under reduced motion', () => {
        const { container } = wrap(<DaybreakSunrise theme={DAYBREAK} />);
        const css = container.querySelector('style')!.textContent!;
        expect(css).toMatch(/\.bc-daybreak-rise\{animation:bc-daybreak-rise 1000ms cubic-bezier\(\.16,1,\.3,1\) both\}/);
        expect(css).toMatch(/\.bc-daybreak-check\{[^}]*animation:bc-daybreak-draw 520ms cubic-bezier\(\.16,1,\.3,1\) 520ms both\}/);
        // once: no iteration count, no loop
        expect(css).not.toMatch(/infinite|alternate/);
        // the finished picture, with no motion at all
        expect(css).toMatch(/@media \(prefers-reduced-motion:reduce\)\{\.bc-daybreak-rise,\.bc-daybreak-check\{animation:none\}\.bc-daybreak-check\{stroke-dasharray:none\}\}/);
    });

    it('takes the page colours: the hills wear the action colour', () => {
        const { container } = wrap(<DaybreakSunrise theme={{ ...DAYBREAK, secondary: '#15803D' }} />);
        const hills = Array.from(container.querySelectorAll('svg > path')).map((p) => p.getAttribute('fill'));
        expect(hills).toEqual(['#15803D', '#15803D']);
    });

    it('sits on the ending page without a picture half, and a picture layout leaves the scene out', () => {
        const ending = (layout: FormSlideLayout) =>
            wrap(
                <LayoutWrapper theme={DAYBREAK} disabled showDesktopLayout layout={layout} artworkBand={layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND}>
                    <h1>Thank you</h1>
                </LayoutWrapper>
            ).container;
        expect(ending(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND).querySelector('[data-testid="daybreak-sunrise"]')).not.toBeNull();
        // the corner sun stays out from under the band (a wedge of it would peek out below)
        expect(ending(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND).innerHTML).not.toContain('data:image/svg+xml');
        expect(themeBackgroundStyle(DAYBREAK, { corner: false }).backgroundImage).toBeUndefined();
        // a page set beside a picture gets no artwork panel from the scene (only marble fills one)
        expect(ending(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT).querySelector('[data-testid="theme-artwork"]')).toBeNull();
    });
});

describe('the scene is not a picture artwork', () => {
    it('does not fill a picture half, make a cover, or change a welcome page layout', () => {
        expect(themeArtwork(DAYBREAK)).toBe('daybreak');
        expect(themePictureArtwork(DAYBREAK)).toBeNull();
        expect(themePictureArtwork(KANTLIJN)).toBe('marble');
        expect(greetingCover(DAYBREAK as FormTheme, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toBeNull();
        const beside = { layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT };
        // away from the marble look, a page beside a picture goes back to the default layout
        expect(welcomeLayoutAfterPreset(beside, KANTLIJN, DAYBREAK)).toBe(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
        // away from the scene, nothing was beside it: the layout is left alone
        expect(welcomeLayoutAfterPreset(beside, DAYBREAK, DEFAULT)).toBeUndefined();
        expect(welcomeLayoutAfterPreset(beside, DEFAULT, DAYBREAK)).toBeUndefined();
    });
});

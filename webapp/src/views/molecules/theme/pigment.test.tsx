import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { applyOps } from '@app/lib/form-ops';
import { FormTheme, GATED_ARTWORKS, GATED_PRESETS, ThemeColors, findPreset, isPresetOffered, offeredArtworks, unofferedArtworkProblem } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';
import { store } from '@app/store/store';
import { contrast } from '@app/utils/color-contrast';
import ChoiceRadioGroup from '@app/views/atoms/choice-radio-group';
import { CHOICE_KEY_FILLS, choiceKeyColours } from '@app/views/atoms/choice';
import LayoutWrapper from '@app/views/organism/layout/layout-wrapper';

import { PIGMENT_RULE, PIGMENT_SUN, PigmentShapes, hasEndingScene, hasPigmentScene, pigmentBandInk, pigmentBandStyle, pigmentRule, pigmentThumbnailStyle } from './pigment-art';
import { ThemeArtworkBand, greetingCover, themePictureArtwork } from './theme-artwork';
import { themeRootProps } from './theme-root';
import { themeBackgroundStyle } from './theme-shared';

const PIGMENT = findPreset('Pigment')!;
const DEFAULT = findPreset('Default')!;

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

describe('the Pigment preset', () => {
    it('is iris on cream with the lettered keys and its scene, and leaves faces and corners to the form', () => {
        expect(PIGMENT).toMatchObject({ title: 'Pigment', primary: '#1A1238', secondary: '#4B35DB', tertiary: '#7C7396', accent: '#FBF7F1', style: 'classic', choiceKeys: 'letters', background: { type: 'color', artwork: 'pigment' } });
        for (const key of ['titleFont', 'bodyFont', 'dataFont', 'titleWidth', 'radius', 'buttonStyle', 'highlight', 'selection', 'inputText'] as const) expect(PIGMENT[key]).toBeUndefined();
    });

    // The pairs the form draws (backend tests/app/services/test_pigment_preset.py checks the same).
    const page = PIGMENT.accent;
    it.each([
        ['questions and text on the page', PIGMENT.primary, page, 4.5],
        ['answers in the white input boxes', PIGMENT.primary, '#FFFFFF', 4.5],
        ['white on the iris (buttons, the chosen row, the check)', '#FFFFFF', PIGMENT.secondary, 4.5],
        ['iris on the page (progress, focus ring)', PIGMENT.secondary, page, 3],
        ['input borders on the page', PIGMENT.tertiary, page, 3],
        ['input borders on white', PIGMENT.tertiary, '#FFFFFF', 3],
        ['the why-we-ask rule on the page', PIGMENT_RULE, page, 3],
        ['ink on the sun-yellow band', PIGMENT.primary, PIGMENT_SUN, 4.5],
        ...CHOICE_KEY_FILLS.map((fill, i) => [`key letter ink on pigment ${i + 1} (${fill})`, PIGMENT.primary, fill, 4.5] as [string, string, string, number])
    ])('%s reads', (_name, foreground, background, minimum) => {
        expect(contrast(foreground, background)).toBeGreaterThanOrEqual(minimum);
    });

    it('is a scene, not a picture artwork', () => {
        expect(hasPigmentScene(PIGMENT) && hasEndingScene(PIGMENT)).toBe(true);
        expect(hasPigmentScene(DEFAULT)).toBe(false);
        expect(themePictureArtwork(PIGMENT)).toBeNull();
        expect(greetingCover(PIGMENT as FormTheme, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)).toBeNull();
    });

    it('is gated with the other scenes: offered, refused and kept as the Daybreak preset is', () => {
        expect(GATED_PRESETS).toContain('Pigment');
        expect(GATED_ARTWORKS.pigment).toBe('Pigment');
        expect(isPresetOffered('Pigment', ['Daybreak'])).toBe(false);
        expect(isPresetOffered('Pigment', ['Pigment'])).toBe(true);
        expect(offeredArtworks(['Pigment'])).toEqual(['marble', 'pigment']);
        expect(unofferedArtworkProblem(PIGMENT, null, 'theme', [])).toBe('theme.background.artwork must be one of: marble.');
        expect(unofferedArtworkProblem(PIGMENT, PIGMENT, 'theme', [])).toBeNull();
        const doc = { title: 'F', builderVersion: 'v2', fields: [] } as any;
        const off = applyOps(doc, [{ op: 'set_theme_preset', name: 'Pigment' }] as any, { offeredGatedPresets: ['Daybreak'] });
        expect(off.results[0].ok).toBe(false);
        expect(off.results[0].message).toContain("There is no theme preset named 'Pigment'");
        expect(off.results[0].message).not.toMatch(/Pick one of:.*Pigment/);
        const on = applyOps(doc, [{ op: 'set_theme_preset', name: 'pigment' }] as any, { offeredGatedPresets: ['Pigment'] });
        expect(on.results[0].ok).toBe(true);
        expect((on.doc as any).theme).toMatchObject({ choiceKeys: 'letters', background: { artwork: 'pigment' } });
        const refusedArt = applyOps(doc, [{ op: 'update_theme', theme: { ...PIGMENT, title: 'Mine' } }] as any, { offeredGatedPresets: [] });
        expect(refusedArt.results[0].ok).toBe(false);
        const worn = { ...doc, theme: PIGMENT };
        expect(applyOps(worn, [{ op: 'update_theme', theme: { ...PIGMENT, title: 'Renamed' } }] as any, { offeredGatedPresets: [] }).results[0].ok).toBe(true);
    });
});

describe('the question page', () => {
    it('has a sun-yellow header band with the form ink on it, a tomato rule and no change to the focus ring', () => {
        expect(pigmentBandStyle()).toEqual({ background: PIGMENT_SUN });
        const root = themeRootProps(PIGMENT);
        expect(root.attributes).toEqual({});
        expect(Object.keys(root.style)).toEqual(['--form-highlight-rule']);
        expect(pigmentRule(PIGMENT)).toBe(PIGMENT_RULE);
        // a page the tomato does not read on gets the ink; a form's own highlight wins
        expect(pigmentRule({ ...PIGMENT, accent: '#FF8A73' })).toBe(PIGMENT.primary);
        expect(themeRootProps({ ...PIGMENT, highlight: '#1035A8' }).style['--form-highlight-rule' as keyof React.CSSProperties]).not.toBe(PIGMENT_RULE);
    });

    it('keeps every piece of text and every icon on the band at 4.5:1: the theme ink where it reads there, else the preset ink', () => {
        expect(pigmentBandInk(PIGMENT)).toBe(PIGMENT.primary);
        expect(contrast('#6E6585', PIGMENT_SUN)).toBeLessThan(4.5);
        expect(pigmentBandInk({ ...PIGMENT, primary: '#6E6585' })).toBe('#1A1238');
        expect(pigmentBandInk({ ...PIGMENT, primary: '#FFFFFF' })).toBe('#1A1238');
        expect(pigmentBandInk({ ...PIGMENT, primary: '#3B2F63' })).toBe('#3B2F63');
        expect(contrast(pigmentBandInk({ ...PIGMENT, primary: '#6E6585' }), PIGMENT_SUN)).toBeGreaterThanOrEqual(4.5);
    });

    it('is a plain cream ground, with the band only in the picker thumbnail', () => {
        expect(themeBackgroundStyle(PIGMENT).backgroundImage).toBeUndefined();
        expect(themeBackgroundStyle(PIGMENT).backgroundColor).toBe('#FBF7F1');
        expect(themeBackgroundStyle(PIGMENT, { compact: true })).toMatchObject(pigmentThumbnailStyle());
        expect(String(pigmentThumbnailStyle().backgroundImage)).toContain(PIGMENT_SUN);
        expect(themeBackgroundStyle(DEFAULT, { compact: true }).backgroundImage).toBeUndefined();
    });

    it('puts the lettered pigment keys on the options and fills the chosen row solid iris', () => {
        const options = ['North', 'South', 'East'].map((label, index) => ({ value: `v${index}`, label, key: `k${index}` }));
        const { container } = wrap(<ChoiceRadioGroup options={options} value="v1" onChange={() => {}} theme={PIGMENT} labelledBy="q" />);
        const keys = Array.from(container.querySelectorAll<HTMLElement>('[data-choice-key]'));
        expect(keys.map((key) => key.textContent)).toEqual(['A', 'B', 'C']);
        expect(keys.map((key) => key.style.color)).toEqual(['rgb(26, 18, 56)', 'rgb(26, 18, 56)', 'rgb(26, 18, 56)']);
        const chosen = container.querySelector<HTMLElement>('[aria-checked="true"]')!;
        expect(chosen.style.background).toBe('var(--form-highlight-solid, #4B35DB)');
        expect(chosen.querySelector('[data-choice-check]')).not.toBeNull();
        // the letter, not the colour, names the key: every pigment holds the ink at 4.5:1
        CHOICE_KEY_FILLS.forEach((fill, index) => expect(contrast(choiceKeyColours(PIGMENT, index).ink, fill)).toBeGreaterThanOrEqual(4.5));
    });
});

describe('the ending', () => {
    it('draws the ring (the one thing in ink on the yellow band) in an ink that reads on it, for any theme', () => {
        const ring = (theme: typeof PIGMENT) => wrap(<ThemeArtworkBand theme={theme} />).container.querySelector('[data-shape="ring"]')!.getAttribute('stroke');
        expect(ring(PIGMENT)).toBe(PIGMENT.primary);
        expect(ring({ ...PIGMENT, primary: '#6E6585' })).toBe('#1A1238');
    });

    // shapes: [name, x0, y0, x1, y1] in the 320 x 160 box (from the attributes)
    const boxes: Record<string, [number, number, number, number]> = {
        circle: [76 - 16, 50 - 16, 76 + 16, 50 + 16],
        square: [226, 26, 256, 56],
        triangle: [236, 104, 268, 134],
        'half-circle': [50, 132 - 26, 102, 132],
        ring: [286 - 11 - 3, 86 - 11 - 3, 286 + 11 + 3, 86 + 11 + 3]
    };

    it('is the ending band of a Pigment form: an iris disc with the check and five flat shapes, decorative', () => {
        const { container } = wrap(<ThemeArtworkBand theme={PIGMENT} />);
        const band = container.querySelector('[data-testid="pigment-shapes"]')!;
        expect(band).not.toBeNull();
        expect(band.getAttribute('aria-hidden')).toBe('true');
        expect(band.getAttribute('style')).toContain('rgb(255, 198, 46)');
        const shapes = Array.from(band.querySelectorAll('[data-shape]'));
        expect(shapes.map((shape) => shape.getAttribute('data-shape'))).toEqual(['circle', 'square', 'triangle', 'half-circle', 'ring']);
        // the disc is the iris, the check is white
        const disc = band.querySelector('circle[r="46"]')!;
        expect(disc.getAttribute('fill')).toBe('#4B35DB');
        expect(band.querySelector('path[stroke="#FFFFFF"]')).not.toBeNull();
        expect(band.innerHTML).not.toMatch(/<(image|img|script|foreignObject)|href=/i);
        // nothing else is drawn: the disc, the check and the five shapes
        expect(band.querySelectorAll('svg > *')).toHaveLength(7);
    });

    it('keeps the whole picture inside its band with air around it, and every shape clear of the box edges', () => {
        const { container } = wrap(<PigmentShapes theme={PIGMENT} />);
        const band = container.querySelector('[data-testid="pigment-shapes"]')!.getAttribute('class')!;
        const svg = container.querySelector('[data-testid="pigment-picture"]')!;
        const cls = svg.getAttribute('class')!;
        // 150px band, 128px picture on a phone (11px above and below); 200px and 160px from sm (20px)
        expect(band).toContain('h-[150px]');
        expect(band).toContain('sm:h-[200px]');
        expect(cls).toContain('h-[128px]');
        expect(cls).toContain('sm:h-[160px]');
        expect(svg.getAttribute('viewBox')).toBe('0 0 320 160');
        for (const [name, [x0, y0, x1, y1]] of Object.entries(boxes)) {
            expect(x0, name).toBeGreaterThanOrEqual(8);
            expect(y0, name).toBeGreaterThanOrEqual(8);
            expect(x1, name).toBeLessThanOrEqual(312);
            expect(y1, name).toBeLessThanOrEqual(152);
        }
        // the disc, too (r 46 about 160,80)
        expect(160 - 46).toBeGreaterThanOrEqual(8);
        expect(80 + 46).toBeLessThanOrEqual(152);
    });

    it('pops the shapes in once, staggered over about 0.7 s, and has them placed under reduced motion', () => {
        const { container } = wrap(<PigmentShapes theme={PIGMENT} />);
        const css = container.querySelector('style')!.textContent!;
        expect(css).toMatch(/animation:bc-pigment-pop 360ms cubic-bezier\(\.34,1\.56,\.64,1\) both/);
        const delays = Array.from(css.matchAll(/data-n="(\d)"\]\{animation-delay:(\d+)ms\}/g)).map((m) => Number(m[2]));
        expect(delays).toEqual([0, 80, 160, 240, 340]);
        // the last shape is done at 340 + 360 = 700 ms
        expect(Math.max(...delays) + 360).toBe(700);
        expect(css).not.toMatch(/infinite|alternate/);
        // the finished picture is the placed one: the animation ends at no transform, reduced motion has none at all
        expect(css).toMatch(/@keyframes bc-pigment-pop\{from\{transform:scale\(0\)\}to\{transform:none\}\}/);
        expect(css).toMatch(/@media \(prefers-reduced-motion:reduce\)\{\.bc-pigment-pop\{animation:none\}\}/);
    });

    it('is one composition: the message starts right under the picture, and a page beside a picture gets no band', () => {
        const ending = (layout: FormSlideLayout) =>
            wrap(
                <LayoutWrapper theme={PIGMENT} disabled showDesktopLayout layout={layout} artworkBand={layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND}>
                    <h1>Thank you</h1>
                </LayoutWrapper>
            ).container;
        const page = ending(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
        expect(page.querySelector('[data-testid="pigment-shapes"]')).not.toBeNull();
        expect(page.querySelector('[data-testid="daybreak-sunrise"]')).toBeNull();
        const cls = page.querySelector('.\\@container\\/page')!.getAttribute('class')!;
        expect(cls).toContain('pt-4');
        expect(cls).not.toContain('before:flex-[2]');
        expect(ending(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT).querySelector('[data-testid="theme-artwork"]')).toBeNull();
        // a question page keeps its optical centring
        const question = wrap(
            <LayoutWrapper theme={PIGMENT} disabled showDesktopLayout>
                <h1>Question</h1>
            </LayoutWrapper>
        ).container.querySelector('.\\@container\\/page')!.getAttribute('class')!;
        expect(question).toContain('before:flex-[2]');
    });
});

describe('no other preset moved', () => {
    it('Default and the others do not wear the scene or the keys', () => {
        for (const preset of ThemeColors.filter((theme) => theme.title !== 'Pigment')) {
            expect(hasPigmentScene(preset)).toBe(false);
            expect(preset.choiceKeys == null).toBe(true);
        }
    });
});

// The Pigment Leaflet preset: the Leaflet style in the Pigment look. The one new renderer decision: the Leaflet section bar is
// the sun-yellow band (with the ink that reads on it), the intro band under it a pale sun tint, and the separate Pigment band
// is not drawn. The condition is exactly "style leaflet AND artwork pigment": Leaflet, Pigment and every other preset draw
// what they did.
import React from 'react';

import { cleanup, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { GATED_PRESETS, PIGMENT_BAND, PIGMENT_BAND_FALLBACK_INK, PIGMENT_BAND_TINT, PIGMENT_LEAFLET_PRESET, ThemeColors, findPreset, isPresetOffered } from '@app/constants/theme';
import { applyOps } from '@app/lib/form-ops';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';
import { contrast } from '@app/utils/color-contrast';
import { hasSunBar } from '@app/views/molecules/theme/pigment-art';
import { leafletColours } from '@app/views/molecules/theme/theme-shared';

import FormSlide from './form-slide';
import ThankyouPage from './thankyou-page';
import WelcomePage from './welcome-page';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const BLEND = findPreset('Pigment Leaflet')!;
const LEAFLET = findPreset('Leaflet')!;
const PIGMENT = findPreset('Pigment')!;
const rgb = (hex: string) => `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(', ')})`;

const question = (id: string, type: FieldTypes, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type, title: `Question ${id}`, ...extra });
const intro = (id: string, content: any[]): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.TEXT, title: { type: 'doc', content } as any });
const slide = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields } });

const open = (theme: Record<string, unknown>) =>
    store.dispatch(
        setForm({
            formId: 'blend-form',
            title: 'Open day feedback',
            theme,
            welcomePage: { description: 'Two short pages.' },
            fields: [
                slide('s1', 0, [question('name', FieldTypes.SHORT_TEXT, { validations: { required: true } })]),
                slide('s2', 1, [
                    intro('t2', [
                        { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'About your visit' }] },
                        { type: 'paragraph', content: [{ type: 'text', text: 'Tell us how it went.' }] }
                    ]),
                    question('travel', FieldTypes.MULTIPLE_CHOICE, {
                        properties: {
                            choices: [
                                { id: 'a', value: 'Walking' },
                                { id: 'b', value: 'Bike' }
                            ],
                            whyWeAsk: 'So we can plan the car park.'
                        } as any
                    })
                ])
            ]
        } as any)
    );

const Themed = ({ children }: { children: React.ReactNode }) => {
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme((store.getState() as any).form.theme);
    }, []);
    return <>{children}</>;
};
const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Themed>{node}</Themed>
            </Provider>
        </ReduxProvider>
    );

describe('the preset', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
    });
    afterEach(cleanup);

    it("is Leaflet's style in Pigment's colours, keys and artwork, named in one constant", () => {
        expect(PIGMENT_LEAFLET_PRESET).toBe('Pigment Leaflet');
        expect(BLEND).toMatchObject({ title: PIGMENT_LEAFLET_PRESET, style: 'leaflet', choiceKeys: 'letters', background: { type: 'color', artwork: 'pigment' } });
        for (const key of ['primary', 'secondary', 'tertiary', 'accent'] as const) expect(BLEND[key]).toBe(PIGMENT[key]);
        // a third preset, after the two it blends
        expect(ThemeColors.map((preset) => preset.title).slice(-3)).toEqual(['Daybreak', 'Pigment', 'Pigment Leaflet']);
    });

    it('is gated with the Pigment preset: offered when the server offers it, a stored one keeps rendering and saving', () => {
        expect(GATED_PRESETS).toContain(PIGMENT_LEAFLET_PRESET);
        expect(isPresetOffered(PIGMENT_LEAFLET_PRESET, ['Pigment'])).toBe(false);
        expect(isPresetOffered(PIGMENT_LEAFLET_PRESET, [PIGMENT_LEAFLET_PRESET])).toBe(true);
        const doc = { title: 'F', builderVersion: 'v2', fields: [] } as any;
        // off: refused as an unknown preset, the name not listed among the choices
        const off = applyOps(doc, [{ op: 'set_theme_preset', name: 'Pigment Leaflet' }] as any, { offeredGatedPresets: ['Daybreak'] });
        expect(off.results[0].ok).toBe(false);
        expect(off.results[0].message).toContain("There is no theme preset named 'Pigment Leaflet'");
        expect(off.results[0].message).not.toMatch(/Pick one of:.*Pigment Leaflet/);
        // on: applied, with the style, the keys and the artwork
        const on = applyOps(doc, [{ op: 'set_theme_preset', name: 'pigment leaflet' }] as any, { offeredGatedPresets: [PIGMENT_LEAFLET_PRESET] });
        expect(on.results[0].ok).toBe(true);
        expect((on.doc as any).theme).toMatchObject({ title: 'Pigment Leaflet', style: 'leaflet', choiceKeys: 'letters', background: { artwork: 'pigment' } });
        // off again: a form that wears it still edits (its theme is stored inline)
        const worn = { ...doc, theme: BLEND };
        expect(applyOps(worn, [{ op: 'update_theme', theme: { ...BLEND, title: 'Renamed' } }] as any, { offeredGatedPresets: [] }).results[0].ok).toBe(true);
    });
});

describe('the branch condition: the Leaflet style AND the Pigment artwork, nothing else', () => {
    it('is true for the preset only, among every preset', () => {
        expect(ThemeColors.filter((preset) => hasSunBar(preset)).map((preset) => preset.title)).toEqual(['Pigment Leaflet']);
        expect(hasSunBar(LEAFLET)).toBe(false);
        expect(hasSunBar(PIGMENT)).toBe(false);
        expect(hasSunBar(null)).toBe(false);
        expect(hasSunBar(undefined)).toBe(false);
        // a custom theme that has both takes the bar, one that has either does not
        expect(hasSunBar({ ...LEAFLET, background: { type: 'color', artwork: 'pigment' } })).toBe(true);
        expect(hasSunBar({ ...PIGMENT, style: 'leaflet' })).toBe(true);
        expect(hasSunBar({ ...LEAFLET, background: { type: 'color', artwork: 'daybreak' } })).toBe(false);
        expect(hasSunBar({ ...LEAFLET, background: { type: 'color' } })).toBe(false);
        expect(hasSunBar({ ...PIGMENT, style: 'classic' })).toBe(false);
    });

    it('leaves the Leaflet colours of every other preset exactly as they were', () => {
        for (const preset of ThemeColors.filter((theme) => !hasSunBar(theme))) {
            const colours = leafletColours(preset);
            expect(colours.bar, preset.title).toBe(preset.secondary);
            expect(colours.barInk, preset.title).toBe('#ffffff');
            expect(colours.introInk, preset.title).toBe(preset.primary);
            expect(colours.band, preset.title).not.toBe(PIGMENT_BAND_TINT);
        }
    });

    it('gives the blend the sun bar, its ink and the sun tint, every pair reading', () => {
        const colours = leafletColours(BLEND);
        expect(colours.bar).toBe(PIGMENT_BAND);
        expect(colours.band).toBe(PIGMENT_BAND_TINT);
        expect(colours.barInk).toBe(BLEND.primary);
        expect(contrast(colours.barInk, colours.bar!)).toBeGreaterThanOrEqual(4.5);
        expect(contrast(colours.introInk!, colours.band)).toBeGreaterThanOrEqual(7);
        // the bar's ink holds 4.5:1 for creator-edited colours (the band-ink rule), the intro ink 7:1
        const faint = { ...BLEND, primary: '#6E6585' };
        expect(leafletColours(faint).barInk).toBe(PIGMENT_BAND_FALLBACK_INK);
        expect(leafletColours(faint).introInk).toBe(PIGMENT_BAND_FALLBACK_INK);
        expect(contrast(leafletColours(faint).barInk, PIGMENT_BAND)).toBeGreaterThanOrEqual(4.5);
    });
});

describe('the pages', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
    });
    afterEach(cleanup);

    it('a question page has ONE band: the section bar is the sun band, the intro band a sun tint, the header row plain paper', async () => {
        open(BLEND);
        wrap(<FormSlide index={1} isPreviewMode />);
        const bar = await screen.findByTestId('leaflet-section-bar');
        expect(bar.style.background).toBe(rgb(PIGMENT_BAND));
        expect(bar.style.color).toBe(rgb(BLEND.primary));
        expect(within(bar).getByTestId('leaflet-section-numeral').textContent).toBe('2');
        expect(screen.getByTestId('leaflet-intro-band').style.background).toBe(rgb(PIGMENT_BAND_TINT));
        // the header row above stays Leaflet's: the page colour, not the yellow, and not the band's ink
        const header = screen.getByRole('button', { name: 'Back' }).closest<HTMLElement>('div.absolute')!;
        expect(header.style.background).toBe(rgb(BLEND.accent));
        expect(header.style.background).not.toBe(rgb(PIGMENT_BAND));
        // the numerals, the margin note rule, the button and the selected state stay on the iris
        expect(screen.getByTestId('question-number').style.color).toBe(rgb(BLEND.secondary));
        expect(screen.getByText('So we can plan the car park.').closest('p')?.className).toContain('border-l-[3px]');
    });

    it('Leaflet keeps its navy bar with white text, and Pigment its band with no section bar', async () => {
        open(LEAFLET);
        wrap(<FormSlide index={1} isPreviewMode />);
        const bar = await screen.findByTestId('leaflet-section-bar');
        expect(bar.style.background).toBe(rgb(LEAFLET.secondary));
        expect(bar.style.color).toBe('rgb(255, 255, 255)');
        expect(screen.getByTestId('leaflet-intro-band').style.background).not.toBe(rgb(PIGMENT_BAND_TINT));
        cleanup();
        open(PIGMENT);
        wrap(<FormSlide index={1} isPreviewMode />);
        const header = (await screen.findByRole('button', { name: 'Back' })).closest<HTMLElement>('div.absolute')!;
        expect(header.style.background).toBe(rgb(PIGMENT_BAND));
        expect(screen.queryByTestId('leaflet-section-bar')).toBeNull();
    });

    it('the welcome page cover is the sun bar with the form title in ink', async () => {
        open(BLEND);
        wrap(<WelcomePage isPreviewMode />);
        const bar = await screen.findByTestId('leaflet-section-bar');
        expect(bar.style.background).toBe(rgb(PIGMENT_BAND));
        expect(within(bar).getByRole('heading', { level: 1, name: 'Open day feedback' })).toBeInTheDocument();
        expect(screen.getByTestId('leaflet-intro-band').style.background).toBe(rgb(PIGMENT_BAND_TINT));
    });

    it('the ending continues the shapes band with the sun bar: no hairline row between them', async () => {
        open(BLEND);
        wrap(<ThankyouPage isPreviewMode />);
        const bar = await screen.findByTestId('leaflet-section-bar');
        expect(bar.style.background).toBe(rgb(PIGMENT_BAND));
        expect(bar.previousElementSibling?.getAttribute('aria-hidden')).not.toBe('true');
        cleanup();
        // every other Leaflet form keeps the top row above its bar
        open(LEAFLET);
        wrap(<ThankyouPage isPreviewMode />);
        const navy = await screen.findByTestId('leaflet-section-bar');
        expect(navy.previousElementSibling?.getAttribute('aria-hidden')).toBe('true');
    });
});

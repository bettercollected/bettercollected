// The sun-yellow band of the Pigment scene is the header bar of a question page. Every piece of text and every icon drawn
// on it (the Back control with its chevron, the page count) takes an ink that reads at 4.5:1 on the yellow: the theme's
// `primary` where it does, else the preset's dark ink. The organisation chip has its own white ground and is not on the band.
import React from 'react';

import { cleanup, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PIGMENT_BAND, PIGMENT_BAND_FALLBACK_INK, findPreset } from '@app/constants/theme';
import { FieldTypes } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';
import { contrast } from '@app/utils/color-contrast';
import { pigmentBandInk } from '@app/views/molecules/theme/pigment-art';

import FormSlide from './form-slide';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const PIGMENT = findPreset('Pigment')!;
const rgb = (hex: string) => `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(', ')})`;

const open = (theme: Record<string, unknown>) =>
    store.dispatch(
        setForm({
            formId: 'pigment-form',
            title: 'Open day feedback',
            theme,
            fields: [
                { id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your name' }] } },
                { id: 's2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'city', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your city' }] } }
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

const draw = () =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Themed>
                    <FormSlide index={1} isPreviewMode />
                </Themed>
            </Provider>
        </ReduxProvider>
    );

/** The header bar, its Back control and its page count, as drawn. */
const band = async () => {
    const back = await screen.findByRole('button', { name: 'Back' });
    const count = document.querySelector<HTMLElement>('[data-page-start]')!;
    const bar = back.closest<HTMLElement>('div.absolute')!;
    return { bar, back, count };
};

describe('the ink on the Pigment band', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
    });
    afterEach(cleanup);

    it('keeps the preset ink on the band: the page count and Back are the theme primary, 11.3:1', async () => {
        open(PIGMENT);
        draw();
        const { bar, back, count } = await band();
        expect(bar.style.background).toBe(rgb(PIGMENT_BAND));
        expect(back.style.color).toBe(rgb(PIGMENT.primary));
        expect(count.parentElement!.style.color).toBe(rgb(PIGMENT.primary));
        expect(contrast(PIGMENT.primary, PIGMENT_BAND)).toBeGreaterThanOrEqual(4.5);
    });

    it('falls back to the dark ink for a custom primary that does not read on the band (#6E6585, 3.46:1), on Back and the page count alike', async () => {
        expect(contrast('#6E6585', PIGMENT_BAND)).toBeLessThan(4.5);
        open({ ...PIGMENT, primary: '#6E6585' });
        draw();
        const { back, count } = await band();
        expect(back.style.color).toBe(rgb(PIGMENT_BAND_FALLBACK_INK));
        expect(count.parentElement!.style.color).toBe(rgb(PIGMENT_BAND_FALLBACK_INK));
        expect(contrast(PIGMENT_BAND_FALLBACK_INK, PIGMENT_BAND)).toBeGreaterThanOrEqual(4.5);
    });

    it('keeps a custom primary that does read on the band', async () => {
        open({ ...PIGMENT, primary: '#3B2F63' });
        draw();
        const { back } = await band();
        expect(back.style.color).toBe(rgb('#3B2F63'));
    });

    it('does not touch a form without the Pigment artwork: its own primary, whatever the band would need', async () => {
        open({ ...PIGMENT, primary: '#6E6585', background: { type: 'color' } });
        draw();
        const { bar, back, count } = await band();
        expect(bar.style.background).not.toBe(rgb(PIGMENT_BAND));
        expect(back.style.color).toBe(rgb('#6E6585'));
        expect(count.parentElement!.style.color).toBe(rgb('#6E6585'));
    });

    it('is white on neither: white is 1.57:1 on the band', () => {
        expect(contrast('#FFFFFF', PIGMENT_BAND)).toBeLessThan(2);
        for (const primary of ['#FFFFFF', '#6E6585', undefined, 'red']) expect(pigmentBandInk({ ...PIGMENT, primary } as any)).toBe(PIGMENT_BAND_FALLBACK_INK);
        expect(pigmentBandInk(PIGMENT)).toBe(PIGMENT.primary);
    });
});

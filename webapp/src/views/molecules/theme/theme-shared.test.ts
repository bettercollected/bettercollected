import { describe, expect, it } from 'vitest';

import { THEME_STYLES, ThemeColors } from '@app/constants/theme';

import { LEAFLET_SIGNAL_RED, REQUIRED_RED, contrast, leafletColours, mixHex, requiredMarkColour, softInk, styleTokens } from './theme-shared';

describe('style tokens', () => {
    it('maps each style to its register, classic by default', () => {
        expect(styleTokens(undefined).key).toBe('classic');
        expect(styleTokens('classic')).toMatchObject({ inputRadius: '6px', solidSelection: false, divider: false, ruledChoices: false, numbered: false });
        expect(styleTokens('sheet')).toMatchObject({ inputRadius: '4px', divider: true, solidSelection: false, ruledChoices: false, numbered: false });
        expect(styleTokens('studio')).toMatchObject({ inputRadius: '0px', solidSelection: true, ruledChoices: false, numbered: false });
        expect(styleTokens('leaflet')).toMatchObject({ key: 'leaflet', inputRadius: '4px', solidSelection: false, divider: false, ruledChoices: true, numbered: true });
    });

    it('knows every style the model allows', () => {
        expect(THEME_STYLES.map((style) => styleTokens(style).key)).toEqual(['classic', 'sheet', 'studio', 'leaflet']);
    });
});

describe('derived colours', () => {
    it('mixes two colours', () => {
        expect(mixHex('#000000', '#FFFFFF', 0.5)).toBe('#808080');
        expect(mixHex('#0B3D91', '#FFFFFF', 1)).toBe('#0B3D91');
        expect(mixHex('#0B3D91', '#FFFFFF', 0)).toBe('#FFFFFF');
    });

    it.each(ThemeColors.map((theme) => [theme.title, theme]))('%s: descriptions stay at 7:1 and the required marker at 4.5:1 on the page', (_title, theme) => {
        expect(contrast(softInk(theme), theme.accent)).toBeGreaterThanOrEqual(7);
        expect(contrast(requiredMarkColour(theme), theme.accent)).toBeGreaterThanOrEqual(4.5);
    });

    it('keeps the danger red where it passes and falls back to the ink where it does not', () => {
        expect(requiredMarkColour({ primary: '#101828', accent: '#FFFFFF' })).toBe(REQUIRED_RED);
        // Ocean's tinted ground puts the red at about 4.2:1.
        expect(requiredMarkColour({ primary: '#111827', accent: '#DBEAFE' })).toBe('#111827');
    });
});

describe('the Leaflet preset', () => {
    const leaflet = ThemeColors.find((theme) => theme.title === 'Leaflet')!;

    it('is navy on white with near-black ink, and switches the form to the Leaflet style', () => {
        expect(leaflet).toMatchObject({ primary: '#1A1A1A', secondary: '#0B3D91', tertiary: '#6B7A99', accent: '#FFFFFF', style: 'leaflet' });
    });

    it('passes every role the way theme.ts documents', () => {
        expect(contrast(leaflet.primary, leaflet.accent)).toBeGreaterThanOrEqual(7); // questions
        expect(contrast(leaflet.primary, '#FFFFFF')).toBeGreaterThanOrEqual(4.5); // answers in white inputs
        expect(contrast('#FFFFFF', leaflet.secondary)).toBeGreaterThanOrEqual(4.5); // white on buttons and section bars
        expect(contrast(leaflet.tertiary, leaflet.accent)).toBeGreaterThanOrEqual(3); // control edges
    });

    it('derives a band the ink reads on at 7:1, and the signal red only where it passes', () => {
        const colours = leafletColours(leaflet);
        expect(colours.band).not.toBe(leaflet.accent);
        expect(contrast(leaflet.primary, colours.band)).toBeGreaterThanOrEqual(7);
        expect(colours.required).toBe(LEAFLET_SIGNAL_RED);
        expect(contrast(colours.required, leaflet.accent)).toBeGreaterThanOrEqual(4.5);
        expect(requiredMarkColour(leaflet)).toBe(LEAFLET_SIGNAL_RED);
    });

    it.each(ThemeColors.map((theme) => [theme.title, theme]))('Leaflet dressing on %s keeps text legible', (_title, theme) => {
        const colours = leafletColours({ ...theme, style: 'leaflet' });
        expect(contrast(theme.primary, colours.band)).toBeGreaterThanOrEqual(7);
        expect(contrast(colours.required, theme.accent)).toBeGreaterThanOrEqual(4.5);
    });
});

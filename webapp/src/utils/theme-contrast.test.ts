// Every built-in theme preset meets WCAG AA contrast wherever the respondent
// form puts one of its colours on another, text included (the button and
// border colours as text, the date picker). axe cannot measure contrast in
// jsdom (no layout), so the presets are checked from their colour values here,
// and the derived text colours are checked on palettes no preset uses.
import { describe, expect, it } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { REQUIRED_RED, mixHex } from '@app/views/molecules/theme/theme-shared';

import { AA_NON_TEXT, AA_TEXT, contrast, hexChannels, legibleOn } from './color-contrast';
import { FOCUS_RING, actionText, calendarColours, themeContrastChecks } from './theme-contrast';

describe('contrast', () => {
    it('follows the WCAG formula', () => {
        expect(contrast('#000000', '#FFFFFF')).toBeCloseTo(21, 5);
        expect(contrast('#FFFFFF', '#000000')).toBeCloseTo(21, 5);
        expect(contrast('#767676', '#FFFFFF')).toBeCloseTo(4.54, 2);
        expect(contrast('#1649E2', '#1649E2')).toBe(1);
    });

    it('reads short and long hex, with or without #, and ignores an alpha pair', () => {
        expect(hexChannels('#fff')).toEqual([255, 255, 255]);
        expect(hexChannels('0B3D91')).toEqual([11, 61, 145]);
        expect(hexChannels('#0B3D9126')).toEqual([11, 61, 145]);
        expect(contrast('#000', '#fff')).toBeCloseTo(21, 5);
    });

    it('fails every check for a colour it cannot read', () => {
        expect(hexChannels('white')).toBeNull();
        expect(contrast('white', '#000000') >= AA_NON_TEXT).toBe(false);
        expect(
            themeContrastChecks({ primary: 'rgb(0,0,0)', secondary: '#1649E2', tertiary: '#818CA0', accent: '#FFFFFF' })
                .filter((check) => !check.passes)
                .map((check) => check.key)
        ).toEqual(['text', 'answer']);
    });
});

describe('legibleOn', () => {
    it('keeps a colour that already reads at the minimum', () => {
        expect(legibleOn('#1649E2', '#F5F7FB', '#101828')).toBe('#1649E2');
    });

    it('moves a colour towards the ink only as far as it needs', () => {
        const weekday = legibleOn('#818CA0', '#F5F7FB', '#101828');
        expect(contrast(weekday, '#F5F7FB')).toBeGreaterThanOrEqual(AA_TEXT);
        expect(contrast(weekday, '#F5F7FB')).toBeLessThan(6);
        expect(weekday).not.toBe('#101828');
    });

    it('falls back to black or white when the ink does not read either', () => {
        expect(legibleOn('#FFFF00', '#FFFFFF', '#EEEEEE')).toBe('#000000');
        expect(legibleOn('#333333', '#000000', '#111111')).toBe('#FFFFFF');
        expect(legibleOn('teal', '#FFFFFF', 'navy')).toBe('#000000');
    });
});

describe('themeContrastChecks', () => {
    it('names the failing pairings of a palette', () => {
        const pale = { primary: '#9CA3AF', secondary: '#FDE68A', tertiary: '#E5E7EB', accent: '#FFFFFF' };
        expect(
            themeContrastChecks(pale)
                .filter((check) => !check.passes)
                .map((check) => check.key)
        ).toEqual(['text', 'answer', 'button', 'border', 'action']);
    });

    it('covers every place a theme colour is text, the border colour included', () => {
        const keys = themeContrastChecks(ThemeColors[0]).map((check) => check.key);
        expect(keys).toEqual(expect.arrayContaining(['text', 'answer', 'button', 'action-text', 'action-text-on-white', 'calendar-day', 'calendar-weekday', 'calendar-today', 'calendar-selected', 'calendar-nav', 'calendar-focus']));
    });
});

// Stored themes can hold any colours: the derived text colours read on all of them.
const AWKWARD: Array<[string, { primary: string; secondary: string; tertiary: string; accent: string }]> = [
    ['pale on white', { primary: '#9CA3AF', secondary: '#FDE68A', tertiary: '#E5E7EB', accent: '#FFFFFF' }],
    ['light ink on dark', { primary: '#F9FAFB', secondary: '#60A5FA', tertiary: '#374151', accent: '#111827' }],
    ['mid grey ground', { primary: '#777777', secondary: '#888888', tertiary: '#999999', accent: '#808080' }],
    ['saturated ground', { primary: '#FFFFFF', secondary: '#FF0000', tertiary: '#00FF00', accent: '#0000FF' }],
    ['not hex', { primary: 'black', secondary: 'rgb(0, 0, 255)', tertiary: '', accent: '#FAFAFA' }]
];

describe.each(AWKWARD)('derived text colours on a stored %s theme', (_name, theme) => {
    it.each(
        themeContrastChecks(theme as any)
            .filter((check) => check.kind === 'derived')
            .map((check) => [check.label, check] as const)
    )('%s', (_label, check) => {
        expect(check.ratio).toBeGreaterThanOrEqual(check.minimum);
    });
});

describe('the date picker keeps a theme that already passes as it was', () => {
    it.each(ThemeColors.map((theme) => [theme.title, theme] as const))('%s', (_title, theme) => {
        const colours = calendarColours(theme);
        if (contrast(theme.secondary, theme.accent) >= AA_TEXT) expect(colours.day).toBe(theme.secondary);
        if (contrast(theme.tertiary, theme.accent) >= AA_TEXT) expect(colours.weekday).toBe(theme.tertiary);
        expect(colours.background).toBe(theme.accent);
        expect(colours.selectedBackground).toBe(theme.secondary);
        expect(colours.focus).toBe(FOCUS_RING);
        expect(actionText(theme)).toBe(contrast(theme.secondary, theme.accent) >= AA_TEXT ? theme.secondary : colours.day);
    });
});

describe('the date picker focus ring', () => {
    it('keeps the app blue where it reaches 3:1 on the calendar', () => {
        expect(calendarColours({ primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#FFFFFF' }).focus).toBe(FOCUS_RING);
    });

    it.each([
        ['a dark palette', { primary: '#F1F5F9', secondary: '#60A5FA', tertiary: '#94A3B8', accent: '#0F172A' }],
        ['a dark page with no text colour', { secondary: '#60A5FA', accent: '#0F172A' }],
        ['a navy page', { primary: '#FFFFFF', secondary: '#FFFFFF', tertiary: '#FFFFFF', accent: '#0B1F66' }]
    ])('moves the blue towards the ink on %s until it reaches 3:1', (_name, theme) => {
        expect(contrast(FOCUS_RING, theme.accent)).toBeLessThan(AA_NON_TEXT);
        const { focus, background } = calendarColours(theme);
        expect(background).toBe(theme.accent);
        expect(focus).not.toBe(FOCUS_RING);
        expect(contrast(focus, background)).toBeGreaterThanOrEqual(AA_NON_TEXT);
    });
});

describe.each(ThemeColors.map((theme) => [theme.title, theme] as const))('the %s preset', (_title, theme) => {
    it.each(themeContrastChecks(theme).map((check) => [check.label, check] as const))('%s', (_label, check) => {
        expect(check.ratio).toBeGreaterThanOrEqual(check.minimum);
    });

    it('keeps the ink legible on a chosen option (a 10% tint of the button colour)', () => {
        expect(contrast(theme.primary, mixHex(theme.secondary, theme.accent, 26 / 255))).toBeGreaterThanOrEqual(AA_TEXT);
    });

    it('shows the error icon and the submit error on the background', () => {
        expect(contrast(REQUIRED_RED, theme.accent)).toBeGreaterThanOrEqual(AA_NON_TEXT); // question-wrapper error icon
        expect(contrast('#B42318', theme.accent)).toBeGreaterThanOrEqual(AA_TEXT); // form-slide submit error
    });
});

// Every built-in theme preset meets WCAG AA contrast where its colours meet
// on the respondent form. axe cannot measure contrast in jsdom (no layout),
// so the presets are checked from their colour values here.
import { describe, expect, it } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { REQUIRED_RED, mixHex } from '@app/views/molecules/theme/theme-shared';

import { AA_NON_TEXT, AA_TEXT, contrast, hexChannels } from './color-contrast';
import { themeContrastChecks } from './theme-contrast';

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

describe('themeContrastChecks', () => {
    it('names the failing pairings of a palette', () => {
        const pale = { primary: '#9CA3AF', secondary: '#FDE68A', tertiary: '#E5E7EB', accent: '#FFFFFF' };
        expect(
            themeContrastChecks(pale)
                .filter((check) => !check.passes)
                .map((check) => check.key)
        ).toEqual(['text', 'answer', 'button', 'border', 'action']);
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

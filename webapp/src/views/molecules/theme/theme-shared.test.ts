import { describe, expect, it } from 'vitest';

import { ThemeColors } from '@app/constants/theme';

import { REQUIRED_RED, contrast, mixHex, requiredMarkColour, softInk, styleTokens } from './theme-shared';

describe('style tokens', () => {
    it('maps each style to its register, classic by default', () => {
        expect(styleTokens(undefined).key).toBe('classic');
        expect(styleTokens('classic')).toMatchObject({ inputRadius: '6px', solidSelection: false, divider: false });
        expect(styleTokens('sheet')).toMatchObject({ inputRadius: '4px', divider: true, solidSelection: false });
        expect(styleTokens('studio')).toMatchObject({ inputRadius: '0px', solidSelection: true });
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

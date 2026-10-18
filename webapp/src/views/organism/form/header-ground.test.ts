import { describe, expect, it } from 'vitest';

import { ThemeColors } from '@app/constants/theme';

import { headerGround } from './form-slide';

const PATTERNS = ['dots', 'grid', 'stripes', 'columns', 'margin'] as const;

describe('the question page header bar', () => {
    it.each(ThemeColors.flatMap((theme) => PATTERNS.map((pattern) => [theme.title, pattern, theme.accent] as const)))('%s over %s is the page colour, opaque', (_title, pattern, accent) => {
        const ground = headerGround(accent, { type: 'pattern', pattern });
        expect(ground).toMatch(/^#[0-9a-fA-F]{6}$/);
        expect(ground).toBe(accent);
    });

    it('is opaque for the presets that set a pattern', () => {
        const patterned = ThemeColors.filter((theme) => theme.background?.type === 'pattern');
        expect(patterned.map((theme) => theme.title)).toEqual(['Kantlijn', 'Raster']);
        for (const theme of patterned) expect(headerGround(theme.accent, theme.background)).toBe(theme.accent);
    });

    it('is opaque for every preset over a plain page', () => {
        for (const theme of ThemeColors) {
            expect(headerGround(theme.accent, theme.background)).toBe(theme.accent);
            expect(headerGround(theme.accent, { type: 'color' })).toBe(theme.accent);
        }
    });

    it('keeps the translucent, blurred bar over a gradient or an image', () => {
        expect(headerGround('#FFFFFF', { type: 'gradient' })).toBe('#FFFFFFE6');
        expect(headerGround('#FFFFFF', { type: 'image' })).toBe('#FFFFFFE6');
    });
});

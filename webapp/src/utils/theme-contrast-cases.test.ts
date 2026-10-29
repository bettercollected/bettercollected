import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { ThemeColors } from '@app/constants/theme';

import { AA_NON_TEXT, AA_TEXT, contrast } from './color-contrast';
import { themeContrastGuard } from './theme-contrast';

/**
 * The colour pairs and themes shared with the server's publish check
 * (backend/tests/app/services/test_theme_contrast.py runs all of them against
 * services/theme_contrast.py), so the builder's contrast guard and the
 * `theme_contrast` check that guards publishing through the API, the MCP
 * server and the AI assistant can't drift.
 */

interface PairCase {
    name: string;
    foreground: string;
    background: string;
    ratio: number | null;
    display: string | null;
    passesText: boolean;
    passesNonText: boolean;
}

interface ThemeCase {
    name: string;
    theme: Record<string, any>;
    issues: Array<{ key: string; ratio: number; display: string; minimum: number }>;
    fix: Record<string, any> | null;
    imageGround: boolean;
}

const corpus = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/theme-contrast.cases.json'), 'utf-8')) as { pairs: PairCase[]; themes: ThemeCase[] };

/** A ratio as the guard shows it: one decimal, rounded down. */
const display = (ratio: number) => (Math.floor(ratio * 10) / 10).toFixed(1);

describe.each(corpus.pairs.map((pair) => [pair.name, pair] as const))('contrast: %s', (_name, pair) => {
    it('reaches the shared ratio', () => {
        const ratio = contrast(pair.foreground, pair.background);
        if (pair.ratio === null) {
            expect(ratio).toBeNaN();
        } else {
            expect(ratio).toBeCloseTo(pair.ratio, 5);
            expect(display(ratio)).toBe(pair.display);
        }
        expect(ratio >= AA_TEXT).toBe(pair.passesText);
        expect(ratio >= AA_NON_TEXT).toBe(pair.passesNonText);
    });
});

describe('the shared themes', () => {
    it('list every preset with its colours', () => {
        for (const preset of ThemeColors) {
            const shared = corpus.themes.find((theme) => theme.name === `preset ${preset.title}`);
            expect(shared, preset.title).toBeDefined();
            for (const role of ['primary', 'secondary', 'tertiary', 'accent'] as const) expect(shared!.theme[role]).toBe(preset[role]);
            expect(shared!.theme.background).toEqual(preset.background);
            expect(shared!.theme.buttonStyle).toEqual(preset.buttonStyle ?? undefined);
            expect(shared!.issues).toEqual([]);
        }
    });
});

describe.each(corpus.themes.map((theme) => [theme.name, theme] as const))('themeContrastGuard: %s', (_name, shared) => {
    it('finds the shared failures and suggests the shared colours', () => {
        const result = themeContrastGuard(shared.theme as Parameters<typeof themeContrastGuard>[0]);
        expect(result.issues.map((issue) => issue.key)).toEqual(shared.issues.map((issue) => issue.key));
        result.issues.forEach((issue, i) => {
            expect(issue.ratio).toBeCloseTo(shared.issues[i].ratio, 5);
            expect(display(issue.ratio)).toBe(shared.issues[i].display);
            expect(issue.minimum).toBe(shared.issues[i].minimum);
        });
        expect(result.fix).toEqual(shared.fix);
        expect(result.imageGround).toBe(shared.imageGround);
    });
});

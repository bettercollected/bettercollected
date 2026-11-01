import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { ThemeColors } from '@app/constants/theme';

import { AA_NON_TEXT, AA_TEXT, contrast } from './color-contrast';
import { contrastKey, mutedLabelInk, themeContrastChecks, themeContrastGuard } from './theme-contrast';

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

const corpus = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/theme-contrast.cases.json'), 'utf-8')) as { pairs: PairCase[]; themes: ThemeCase[]; keys: Array<{ name: string; a: Record<string, any>; b: Record<string, any>; same: boolean }>; muted: Array<{ name: string; theme: Record<string, any>; ink: string }> };

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

describe.each(corpus.keys.map((pair) => [pair.name, pair] as const))('contrastKey: %s', (_name, shared) => {
    it('is the same, or not, as the server says', () => {
        expect(contrastKey(shared.a) === contrastKey(shared.b)).toBe(shared.same);
    });
});

describe('contrastKey', () => {
    it('reads what the guard reads: themes with the same key get the same verdict', () => {
        for (const shared of corpus.keys.filter((pair) => pair.same && pair.a && pair.b && pair.a.primary && pair.b.primary)) {
            const [a, b] = [shared.a, shared.b].map((theme) => themeContrastGuard(theme as Parameters<typeof themeContrastGuard>[0]));
            expect(a.issues, shared.name).toEqual(b.issues);
            expect(a.imageGround, shared.name).toBe(b.imageGround);
        }
    });
});

describe.each(corpus.muted.map((shared) => [shared.name, shared] as const))('mutedLabelInk: %s', (_name, shared) => {
    it('is the colour the server derives', () => {
        expect(mutedLabelInk(shared.theme)).toBe(shared.ink);
    });
});

describe('the muted labels', () => {
    const onAPage = corpus.muted.filter((c) => c.theme.accent && c.theme.primary && c.theme.background?.type !== 'image');

    it('are a derived check on the page colour, and read there (a gradient has more grounds than that check shows)', () => {
        for (const shared of onAPage.filter((c) => c.theme.background?.type !== 'gradient')) {
            const check = themeContrastChecks(shared.theme as Parameters<typeof themeContrastChecks>[0]).find((c) => c.key === 'muted-label');
            expect(check, shared.name).toBeDefined();
            expect(check!.kind).toBe('derived');
            expect(check!.foreground).toBe(shared.ink);
            expect(check!.passes, shared.name).toBe(true);
        }
    });

    it('are softer than the questions but not under 4.5:1 (nor under the questions where those fail)', () => {
        for (const shared of onAPage) {
            const theme = shared.theme as Parameters<typeof themeContrastGuard>[0];
            const grounds = [theme.accent, ...(theme.background?.type === 'gradient' ? [theme.background.gradientFrom!, theme.background.gradientTo!] : []), ...(theme.background?.type === 'pattern' && theme.background.pattern === 'margin' && contrast(theme.primary, '#FFFFFF') >= AA_TEXT ? ['#FFFFFF'] : [])];
            const lowest = (colour: string) => Math.min(...grounds.map((ground) => contrast(colour, ground)));
            expect(lowest(shared.ink), shared.name).toBeGreaterThanOrEqual(Math.min(AA_TEXT, lowest(theme.primary)) - 1e-9);
            if (!themeContrastGuard(theme).issues.some((issue) => issue.key === 'text')) expect(lowest(shared.ink), shared.name).toBeGreaterThanOrEqual(AA_TEXT);
        }
    });

    it('are measured by the guard as text: a theme whose ink does not read fails once, as text', () => {
        const result = themeContrastGuard({ primary: '#E8ECF8', secondary: '#1649E2', tertiary: '#818CA0', accent: '#FFFFFF', inputText: '#101828' });
        expect(result.issues.map((issue) => issue.key)).toEqual(['text']);
    });
});

import { readFileSync, readdirSync, statSync } from 'fs';
import { join, resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { defaultForm } from '@app/constants/form';
import { ThemeColor, ThemeColors } from '@app/constants/theme';

// The design system in DESIGN.md, held to the stylesheet that implements it.
const css = readFileSync(resolve(__dirname, 'tailwind.css'), 'utf8');
const globals = readFileSync(resolve(__dirname, 'globals.css'), 'utf8');
const token = (name: string) => css.match(new RegExp(`--${name}:\\s*([^;]+);`))?.[1].trim();

const SRC = resolve(__dirname, '../..');
function sourceFiles(dir: string, out: string[] = []): string[] {
    for (const entry of readdirSync(dir)) {
        const path = join(dir, entry);
        if (statSync(path).isDirectory()) sourceFiles(path, out);
        else if (/\.(tsx?|css)$/.test(entry) && !/\.test\.tsx?$/.test(entry)) out.push(path);
    }
    return out;
}
const sources = sourceFiles(SRC).map((path) => ({ path, text: readFileSync(path, 'utf8') }));

describe('palette', () => {
    it('holds the Sireto blue ramp and the primary button face', () => {
        expect(token('color-brand-100')).toBe('#E0E8FF');
        expect(token('color-brand-200')).toBe('#BFD0FF');
        expect(token('color-brand-500')).toBe('#123FC9');
        expect(token('color-brand')).toBe('#123FC9');
        expect(token('color-brand-600')).toBe('#1035A8');
        expect(token('color-brand-700')).toBe('#0E2D8F');
        expect(token('color-action')).toBe('#1649E2');
        expect(token('color-action-hover')).toBe('#123FC9');
        expect(token('color-action-pressed')).toBe('#0E2D8F');
    });

    it('holds one neutral ramp with the Sireto values', () => {
        expect(token('color-black-100')).toBe('#F5F7FB');
        expect(token('color-black-200')).toBe('#F2F4F7');
        expect(token('color-black-300')).toBe('#EAECF0');
        expect(token('color-black-400')).toBe('#D0D5DD');
        expect(token('color-black-600')).toBe('#667085');
        expect(token('color-black-700')).toBe('#344054');
        expect(token('color-black-900')).toBe('#101828');
        expect(token('color-body')).toBe('#5A6478');
        expect(css).not.toMatch(/--color-new-/);
    });

    it('keeps yellow for fills and olive for yellow text', () => {
        expect(token('color-brand-accent')).toBe('#E5AE00');
        expect(token('color-brand-olive')).toBe('#8A6800');
        expect(token('color-success')).toBe('#039855');
    });

    it('leaves no retired blue anywhere in the webapp source', () => {
        const offenders = sources.filter(({ text }) => /#(0764EB|2456CC)\b/i.test(text)).map(({ path }) => path);
        expect(offenders).toEqual([]);
    });
});

describe('type', () => {
    it('loads Instrument Sans and JetBrains Mono through next/font, and nothing from Google at runtime', () => {
        expect(token('font-sans')).toMatch(/^var\(--font-instrument-sans\)/);
        expect(token('font-mono')).toMatch(/^var\(--font-jetbrains-mono\)/);
        expect(globals).not.toMatch(/fonts\.googleapis|fonts\.gstatic/);
        const layout = readFileSync(resolve(SRC, 'app/layout.tsx'), 'utf8');
        expect(layout).toMatch(/Instrument_Sans, JetBrains_Mono } from 'next\/font\/google'/);
    });

    it('has no leftover font aliases', () => {
        expect(css).not.toMatch(/--font-(inter|roboto|comfortaa)\b/);
        expect(sources.filter(({ text }) => /\bfont-(inter|roboto|comfortaa)\b/.test(text)).map(({ path }) => path)).toEqual([]);
    });
});

describe('shape and depth', () => {
    it('sets the UI radius to 6px', () => {
        expect(token('radius')).toBe('6px');
        expect(token('radius-lg')).toBe('8px');
    });

    it('defines exactly one shadow, for floating layers', () => {
        expect(css.match(/--shadow-[\w-]+:/g)).toEqual(['--shadow-large:']);
        expect(css).not.toMatch(/--drop-shadow/);
    });

    it('uses no shadow utility but shadow-large (and shadow-none) in the app', () => {
        const used = new Set<string>();
        for (const { text } of sources) {
            for (const match of text.matchAll(/(?<![\w-])(?:[a-z-]+:)*(shadow-[a-zA-Z0-9-]+|drop-shadow(?:-[a-z0-9]+)?)(?![\w-])/g)) used.add(match[1]);
        }
        expect([...used].filter((name) => !['shadow-large', 'shadow-none'].includes(name))).toEqual([]);
    });

    it('gives every interactive element a 2px Sireto-blue focus outline', () => {
        expect(css).toMatch(/:focus-visible \{\s*outline: 2px solid var\(--focus-ring, var\(--color-brand-500\)\) !important;\s*outline-offset: 3px !important;/);
    });

    it('defines the key edge as a 3px inset bottom edge that a press removes', () => {
        expect(css).toMatch(/@utility key-edge \{\s*box-shadow: inset 0 -3px 0 0 var\(--key-edge/);
        expect(css).toMatch(/&:active:not\(:disabled\) \{\s*box-shadow: none;\s*transform: translateY\(1px\);/);
    });
});

describe('form themes', () => {
    it('retunes only the Default preset', () => {
        const defaults = ThemeColors.find((theme) => theme.title === 'Default');
        expect(defaults).toMatchObject({ primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB' });
        expect(ThemeColor).toMatchObject({ primary: '#101828', secondary: '#1649E2', accent: '#F5F7FB' });
        expect(defaultForm.theme).toMatchObject({ primary: '#101828', secondary: '#1649E2', accent: '#F5F7FB' });
        // Spot-check that the other presets kept their values.
        expect(ThemeColors.find((theme) => theme.title === 'Ocean')).toMatchObject({ secondary: '#1D4ED8', accent: '#DBEAFE' });
        expect(ThemeColors.find((theme) => theme.title === 'Mono')).toMatchObject({ primary: '#101826', secondary: '#101826' });
    });
});

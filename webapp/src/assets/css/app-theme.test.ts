import { readFileSync, readdirSync, statSync } from 'fs';
import { join, resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { THEME_PICTURES } from '@app/components/app-theme/app-theme-previews';
import { PIGMENTS } from '@app/lib/form-hue';
import { contrast } from '@app/utils/color-contrast';

// The two app themes, Daybreak and Pigment (DESIGN.md §1 and "Pigment theme"), held to the stylesheet that implements
// them: every theme sets the same variables, the contrast of every text and control pair is computed from the values
// in the CSS (not copied constants), and what must never be themed stays out of the blocks.
const css = readFileSync(resolve(__dirname, 'tailwind.css'), 'utf8');
const SRC = resolve(__dirname, '../..');

type Theme = 'daybreak' | 'pigment';
const THEMES: Theme[] = ['daybreak', 'pigment'];

/** The rule of a theme (its attribute scope, or its `<html>` mirror): variable to raw value. */
function rule(theme: Theme, kind: 'scope' | 'mirror'): Record<string, string> {
    const selector = kind === 'scope' ? `\\[data-app-theme='${theme}'\\]` : `html:has\\(\\[data-app-theme='${theme}'\\]\\)`;
    const body = css.match(new RegExp(`^${selector} \\{([^}]*)\\}`, 'm'))?.[1] ?? '';
    const out: Record<string, string> = {};
    for (const line of body.replace(/\/\*[\s\S]*?\*\//g, '').split(';')) {
        const match = line.match(/^\s*(--[\w-]+)\s*:\s*([\s\S]+?)\s*$/);
        if (match) out[match[1]] = match[2];
    }
    return out;
}

/** The ramp and `action` tokens of `@theme` (`--color-*`), which a theme may refer to but never declares. */
const themeToken = (name: string) => css.match(new RegExp(`--color-${name}:\\s*([^;]+);`))?.[1].replace(/\/\*.*$/, '').trim();

/** A variable of a theme as a hex colour, following `var()` aliases through the theme and `@theme`. */
function colour(theme: Theme, variable: string): string {
    const scope = rule(theme, 'scope');
    const raw = scope[variable] ?? (variable.startsWith('--color-') ? themeToken(variable.slice(8)) : undefined);
    if (!raw) throw new Error(`${theme} has no ${variable}`);
    const alias = raw.match(/^var\((--[\w-]+)\)$/);
    return (alias ? colour(theme, alias[1]) : raw).toUpperCase();
}

/** A role by the short name tests use: `ink` is `--app-ink`, `series-1` is `--series-1`, `form-hue-0-bg` is itself. */
const role = (theme: Theme, name: string) => colour(theme, name.startsWith('series-') ? `--${name}` : name.startsWith('form-hue-') || name.startsWith('app-') ? `--${name}` : `--app-${name}`);

describe('both themes set the same variables', () => {
    const daybreak = Object.keys(rule('daybreak', 'scope'));
    const pigment = Object.keys(rule('pigment', 'scope'));

    it('has a Daybreak scope, a Pigment scope and an html rule for each, each in its own rule', () => {
        for (const theme of THEMES) {
            expect(Object.keys(rule(theme, 'scope')).length, `${theme} scope`).toBeGreaterThan(50);
            expect(rule(theme, 'mirror'), `${theme} html rule`).toEqual(rule(theme, 'scope'));
        }
        expect(css).not.toMatch(/\[data-app-theme='[a-z]+'\],\s*html:has/);
    });

    it('gives Pigment every variable Daybreak has, and the pigments besides, nothing else', () => {
        expect(daybreak.filter((name) => !pigment.includes(name))).toEqual([]);
        expect(pigment.filter((name) => !daybreak.includes(name)).sort()).toEqual(['--app-pig-ink', '--app-pig-mint', '--app-pig-orchid', '--app-pig-sky', '--app-pig-sun', '--app-pig-tomato']);
    });

    it('puts Pigment after Daybreak, in the scope rules and in the html rules, so Pigment wins where both apply', () => {
        const at = (pattern: string) => css.indexOf(pattern);
        expect(at("[data-app-theme='pigment'] {")).toBeGreaterThan(at("[data-app-theme='daybreak'] {"));
        expect(at("html:has([data-app-theme='pigment']) {")).toBeGreaterThan(at("html:has([data-app-theme='daybreak']) {"));
    });

    it('declares nothing but --app-*, --series-* and --form-hue-* variables in a theme block, and never a ramp', () => {
        for (const theme of THEMES) {
            for (const name of Object.keys(rule(theme, 'scope'))) {
                expect(name, theme).toMatch(/^--(app|series|form-hue)-/);
                expect(name, theme).not.toMatch(/^--color-(brand|black)/);
            }
        }
        // the ramps keep their own `@theme` values, whichever theme is on
        expect(themeToken('brand-500')).toBe('#123FC9');
        expect(themeToken('black-100')).toBe('#F5F7FB');
        expect(themeToken('action')).toBe('#1649E2');
    });

    it('keeps respondent-facing components off the semantic roles (the trust strip and the "Powered by" badge)', () => {
        for (const file of ['views/molecules/trust-layer.tsx', 'components/powered-by.tsx']) {
            let text = '';
            try {
                text = readFileSync(resolve(SRC, file), 'utf8');
            } catch {
                continue;
            }
            expect(text, file).not.toMatch(/\b(bg|text|border|fill|ring|outline)-(canvas|surface|sunken|hairline|ink|copy|app-|series-|sun|coral)/);
        }
    });

    it('lets the action utilities fall back to the frozen blue where no theme scope is around (respondent routes)', () => {
        const inline = css.match(/@theme inline \{([^}]*)\}/)?.[1] ?? '';
        expect(inline).toContain('--color-app-action: var(--app-action, var(--color-action));');
        expect(inline).toContain('--color-app-action-hover: var(--app-action-hover, var(--color-action-hover));');
        expect(inline).toContain('--color-app-action-pressed: var(--app-action-pressed, var(--color-action-pressed));');
        expect(inline).toContain('--color-app-focus-ring: var(--app-focus-ring, var(--color-brand-500));');
        // the focus outline: a form theme's own ring first, then the app theme's, then Sireto blue
        expect(css).toMatch(/outline: 2px solid var\(--focus-ring, var\(--app-focus-ring, var\(--color-brand-500\)\)\) !important;/);
        // a chosen option's edge and the primary button read the role too
        expect(css).toMatch(/@utility option-selected \{[^}]*border-color: var\(--app-action, var\(--color-action\)\);/);
        const button = readFileSync(resolve(SRC, 'shadcn/components/ui/button.tsx'), 'utf8');
        expect(button).toMatch(/primary: 'bg-app-action text-app-on-action hover:bg-app-action-hover active:bg-app-action-pressed/);
    });
});

describe('Daybreak keeps its look through the new roles', () => {
    it('maps each app role to the value it had before', () => {
        expect(role('daybreak', 'action')).toBe('#1649E2');
        expect(role('daybreak', 'action-hover')).toBe('#123FC9');
        expect(role('daybreak', 'action-pressed')).toBe('#0E2D8F');
        expect(role('daybreak', 'on-action')).toBe('#FFFFFF');
        expect(role('daybreak', 'focus-ring')).toBe('#123FC9');
        expect(role('daybreak', 'accent')).toBe('#FFB400');
        expect(role('daybreak', 'accent-tint')).toBe('#FFF1C7');
        expect(role('daybreak', 'accent-ink')).toBe('#6B4700');
        expect(role('daybreak', 'attention')).toBe('#FF6A48');
        expect(role('daybreak', 'attention-tint')).toBe('#FFE4DC');
        expect(role('daybreak', 'attention-ink')).toBe('#A22F14');
    });

    it('keeps the sun and coral names as aliases of the accent and attention roles in both themes', () => {
        for (const theme of THEMES) {
            const scope = rule(theme, 'scope');
            for (const [alias, canonical] of [
                ['sun', 'accent'],
                ['sun-tint', 'accent-tint'],
                ['sun-ink', 'accent-ink'],
                ['coral', 'attention'],
                ['coral-tint', 'attention-tint'],
                ['coral-ink', 'attention-ink']
            ]) {
                expect(scope[`--app-${alias}`], `${theme} ${alias}`).toBe(`var(--app-${canonical})`);
            }
        }
    });
});

/** [foreground, background, needs, what it is]: every text and control pair of the creator app. 4.5 for text, 3 for controls, edges and marks. */
const PAIRS: Array<[string, string, number, string]> = [
    ['ink', 'canvas', 4.5, 'Headings and answers on the canvas'],
    ['ink', 'surface', 4.5, 'Headings and answers on a card'],
    ['copy', 'canvas', 4.5, 'Running text on the canvas'],
    ['copy', 'surface', 4.5, 'Running text on a card'],
    ['copy', 'brand-tint', 4.5, 'Running text on the tint (welcome band)'],
    ['ink-muted', 'canvas', 4.5, 'Labels and captions on the canvas'],
    ['ink-muted', 'surface', 4.5, 'Labels and captions on a card'],
    ['ink-muted', 'sunken', 4.5, 'Neutral status pill'],
    ['on-action', 'action', 4.5, 'Primary button text on its face'],
    ['on-action', 'action-hover', 4.5, 'Primary button text on hover'],
    ['on-action', 'action-pressed', 4.5, 'Primary button text pressed'],
    ['action', 'surface', 3, 'Selected option edge and primary face on a card'],
    ['action', 'canvas', 3, 'Selected option edge on the canvas'],
    ['action', 'brand-tint', 3, 'Selected option edge on its tint'],
    ['focus-ring', 'surface', 3, 'Keyboard focus ring on a card'],
    ['focus-ring', 'canvas', 3, 'Keyboard focus ring on the canvas'],
    ['link', 'surface', 4.5, 'Links on a card'],
    ['link', 'brand-tint', 4.5, 'Active nav item, link on the tint'],
    ['ink', 'brand-tint', 4.5, 'Selected option label'],
    ['control-edge', 'surface', 3, 'Control edge on a card'],
    ['control-edge', 'canvas', 3, 'Control edge on the canvas'],
    ['accent-ink', 'accent-tint', 4.5, 'Accent text on its tint'],
    ['attention-ink', 'attention-tint', 4.5, 'Waiting badge'],
    ['ink', 'accent-tint', 4.5, 'Ink on the accent tint'],
    ['ink', 'attention-tint', 4.5, 'Ink on the attention tint'],
    ['ok', 'ok-tint', 4.5, 'Success pill'],
    ['warn', 'warn-tint', 4.5, 'Warning pill'],
    ['bad', 'bad-tint', 4.5, 'Danger pill'],
    ['info', 'info-tint', 4.5, 'Info pill'],
    ['ok', 'surface', 4.5, 'Success text on a card'],
    ['warn', 'surface', 4.5, 'Warning text on a card'],
    ['bad', 'surface', 4.5, 'Danger text on a card'],
    ['info', 'surface', 4.5, 'Info text on a card'],
    ['bad', 'canvas', 4.5, 'Required asterisk and error text on the canvas'],
    ['ok-fill', 'surface', 3, 'Success icon on a card'],
    ['bad-fill', 'surface', 3, 'Danger icon on a card'],
    ['series-1', 'surface', 3, 'Chart series 1'],
    ['series-2', 'surface', 3, 'Chart series 2'],
    ['series-3', 'surface', 3, 'Chart series 3'],
    ['series-4', 'surface', 3, 'Chart series 4'],
    ['series-5', 'surface', 3, 'Chart series 5'],
    ['series-6', 'surface', 3, 'Chart series 6'],
    ['series-1', 'sunken', 3, 'Bar on its track']
];

describe.each(THEMES)('%s contrast', (theme) => {
    it.each(PAIRS)('%s on %s is at least %s:1 (%s)', (fg, bg, needs) => {
        expect(contrast(role(theme, fg), role(theme, bg))).toBeGreaterThanOrEqual(needs);
    });

    it.each([0, 1, 2, 3, 4])('the ink of form hue %s is at least 4.5:1 on its tile', (index) => {
        expect(contrast(role(theme, `form-hue-${index}-ink`), role(theme, `form-hue-${index}-bg`))).toBeGreaterThanOrEqual(4.5);
    });
});

describe('the pigments', () => {
    const NAMES = PIGMENTS.map((name) => `--app-pig-${name}`);

    it('are the five of lib/form-hue.ts, flat fills with one ink that reads on every one', () => {
        for (const name of NAMES) expect(rule('pigment', 'scope')[name], name).toMatch(/^#[0-9A-F]{6}$/i);
        for (const name of NAMES) expect(contrast(colour('pigment', '--app-pig-ink'), colour('pigment', name)), name).toBeGreaterThanOrEqual(4.5);
    });

    it('are the form tiles of a Pigment workspace, one pigment and the ink for each hue index', () => {
        PIGMENTS.forEach((name, index) => {
            expect(role('pigment', `form-hue-${index}-bg`)).toBe(colour('pigment', `--app-pig-${name}`));
            expect(role('pigment', `form-hue-${index}-ink`)).toBe(colour('pigment', '--app-pig-ink'));
        });
    });

    it('never reach 3:1 on white, so no chart mark, icon or focus ring may use a pigment as its only boundary', () => {
        for (const name of NAMES) expect(contrast(colour('pigment', name), '#FFFFFF'), name).toBeLessThan(3);
    });

    it('are never a text colour: there is no pigment text utility and none is used', () => {
        expect(css).not.toMatch(/--color-(app-)?pig/);
        const offenders: string[] = [];
        const walk = (dir: string) => {
            for (const entry of readdirSync(dir)) {
                const path = join(dir, entry);
                if (statSync(path).isDirectory()) walk(path);
                else if (/\.(tsx?|css)$/.test(entry) && !/\.test\./.test(entry) && /(\btext-pig|text-\[var\(--app-pig|(^|[\s;{])color:\s*[^;}]*--app-pig)/.test(readFileSync(path, 'utf8').replace(/\/\*[\s\S]*?\*\//g, ''))) offenders.push(path.slice(SRC.length + 1));
            }
        };
        walk(SRC);
        expect(offenders).toEqual([]);
    });

    it('are never a primary button face: the action roles are iris, not a pigment', () => {
        const action = colour('pigment', '--app-action');
        for (const name of NAMES) expect(action, name).not.toBe(colour('pigment', name));
        expect(contrast('#FFFFFF', action)).toBeGreaterThanOrEqual(4.5);
    });

    it('keep danger away from tomato: the danger colours are a deeper red than the tomato pigment', () => {
        const tomato = colour('pigment', '--app-pig-tomato');
        for (const name of ['bad', 'bad-fill', 'bad-tint']) expect(role('pigment', name), name).not.toBe(tomato);
        expect(contrast(role('pigment', 'bad-fill'), '#FFFFFF')).toBeGreaterThan(contrast(tomato, '#FFFFFF'));
    });
});

describe('the previews on the Appearance card', () => {
    it.each(THEMES)('draw %s with the colours of its block', (theme) => {
        const p = THEME_PICTURES[theme];
        expect(p.ground, 'canvas').toBe(role(theme, 'canvas'));
        expect(p.card, 'surface').toBe(role(theme, 'surface'));
        expect(p.edge, 'hairline-strong').toBe(role(theme, 'hairline-strong'));
        expect(p.ink, 'ink').toBe(role(theme, 'ink'));
        expect(p.line, 'hairline').toBe(role(theme, 'hairline'));
        expect(p.action, 'action').toBe(role(theme, 'action'));
        expect(p.tiles).toEqual([0, 1, 2, 3, 4].map((index) => role(theme, `form-hue-${index}-bg`)));
    });
});

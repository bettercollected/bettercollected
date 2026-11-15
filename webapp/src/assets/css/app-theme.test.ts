import { readFileSync, readdirSync, statSync } from 'fs';
import { join, resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { THEME_PICTURES } from '@app/components/app-theme/app-theme-previews';
import { PIGMENTS } from '@app/lib/form-hue';
import {
    DANGER_DELTA_E,
    DANGER_HUE,
    DEUTERANOPIA,
    NEIGHBOUR_LUMINANCE,
    PROTANOPIA,
    SECOND_NEIGHBOUR_LUMINANCE,
    SIMULATED_DELTA_E,
    deltaE,
    hueAndSaturation,
    hueDistance
} from '@app/test/colour-vision';
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

describe('the chrome roles stand for the ramp steps they replace in Daybreak', () => {
    it.each([
        ['primary', '--color-brand-500'],
        ['primary-deep', '--color-brand-600'],
        ['primary-soft', '--color-brand-200'],
        ['edge', '--color-black-300'],
        ['edge-strong', '--color-black-400'],
        ['wash', '--color-black-100'],
        ['wash-strong', '--color-black-200'],
        ['control', '--color-control']
    ])('--app-%s is %s in Daybreak', (name, ramp) => {
        expect(rule('daybreak', 'scope')[`--app-${name}`]).toBe(`var(${ramp})`);
        expect(role('daybreak', name)).toBe(colour('daybreak', ramp));
    });

    it('--app-primary-tint is --app-brand-tint in both themes (a variable of its own, so a form root can reset it)', () => {
        for (const theme of THEMES) {
            expect(rule(theme, 'scope')['--app-primary-tint'], theme).toBe('var(--app-brand-tint)');
            expect(role(theme, 'primary-tint')).toBe(role(theme, 'brand-tint'));
        }
    });

    it('are different values in Pigment (iris and warm paper), never a ramp reference', () => {
        for (const name of ['primary', 'primary-deep', 'primary-soft', 'edge', 'edge-strong', 'wash', 'wash-strong', 'control']) {
            expect(rule('pigment', 'scope')[`--app-${name}`], name).toMatch(/^#[0-9A-F]{6}$/i);
            expect(role('pigment', name), name).not.toBe(role('daybreak', name));
        }
    });

    it('become utilities that fall back to the frozen ramp where no scope is around, so a respondent route is unchanged', () => {
        const inline = css.match(/@theme inline \{([^}]*)\}/)?.[1] ?? '';
        for (const [util, variable, ramp] of [
            ['app-primary', 'app-primary', 'color-brand-500'],
            ['app-primary-deep', 'app-primary-deep', 'color-brand-600'],
            ['app-primary-soft', 'app-primary-soft', 'color-brand-200'],
            ['app-primary-tint', 'app-primary-tint', 'color-brand-100'],
            ['app-edge', 'app-edge', 'color-black-300'],
            ['app-edge-strong', 'app-edge-strong', 'color-black-400'],
            ['app-wash', 'app-wash', 'color-black-100'],
            ['app-wash-strong', 'app-wash-strong', 'color-black-200'],
            ['app-control', 'app-control', 'color-control']
        ]) {
            expect(inline).toContain(`--color-${util}: var(--${variable}, var(--${ramp}));`);
        }
    });
});

describe('the shared controls read the chrome roles, and the frozen files do not', () => {
    const read = (path: string) => readFileSync(resolve(SRC, path), 'utf8');

    it.each(['shadcn/components/ui/switch.tsx', 'shadcn/components/ui/checkbox.tsx', 'shadcn/components/ui/radio-group.tsx', 'shadcn/components/ui/tabs.tsx', 'shadcn/components/ui/button.tsx', 'shadcn/components/ui/input.tsx', 'components/ui/route-tab-bar.tsx'])('%s has no blue ramp step', (file) => {
        expect(read(file)).not.toMatch(/(?<![\w-])(?:bg|text|border|ring|outline)-brand-\d/);
    });

    it('keeps every respondent-facing file on the frozen ramps, so a form inside the builder keeps its own look', () => {
        for (const file of ['views/molecules/form/trust-layer.tsx', 'components/ui/powered-by.tsx', 'layouts/top-navbar-layout.tsx', 'app/(auth)/_components/login-view.tsx']) {
            expect(read(file), file).not.toMatch(/(?<![\w-])(?:bg|text|border|ring|outline)-app-(?:primary|edge|wash|control)/);
        }
        const walk = (dir: string): string[] => readdirSync(dir).flatMap((entry) => (statSync(join(dir, entry)).isDirectory() ? walk(join(dir, entry)) : [join(dir, entry)]));
        for (const dir of ['views/molecules/responder-form-fields', 'components/responder-portal', 'views/molecules/theme']) {
            for (const file of walk(resolve(SRC, dir)).filter((path) => /\.tsx?$/.test(path) && !/\.test\./.test(path))) {
                expect(readFileSync(file, 'utf8'), file).not.toMatch(/(?<![\w-])(?:bg|text|border|ring|outline|divide)-app-(?:primary|edge|wash|control)/);
            }
        }
    });
});

describe('the nav group chips', () => {
    it('are drawn by a pseudo-element that only exists inside a Pigment scope, so Daybreak gets no element and no pixel', () => {
        const rules = [...css.matchAll(/^([^\n{}]*data-nav-chip[^\n{]*)\{/gm)].map((match) => match[1].trim());
        expect(rules.length).toBeGreaterThanOrEqual(4);
        for (const selector of rules) expect(selector).toMatch(/^\[data-app-theme='pigment'\] \[data-nav-chip/);
        // the Daybreak scope never sets the chip variable: the chip would be unpainted there even if it matched
        expect(rule('daybreak', 'scope')['--app-nav-chip']).toBeUndefined();
        const drawer = readFileSync(resolve(SRC, 'components/sidebar/dashboard-drawer.tsx'), 'utf8');
        // only an attribute on the label that exists today: no element, no text
        expect(drawer).toMatch(/data-nav-chip=\{navGroups\.indexOf\(group\) % 3\}/);
        expect(drawer).not.toMatch(/data-nav-chip[^>]*>\s*<(?:span|i|svg)/);
    });

    it('use three of the five pigments, fills only', () => {
        for (const [index, pigment] of [
            ['0', 'tomato'],
            ['1', 'sky'],
            ['2', 'mint']
        ]) {
            expect(css).toMatch(new RegExp(`\\[data-nav-chip='${index}'\\] \\{\\s*--app-nav-chip: var\\(--app-pig-${pigment}\\);`));
        }
        expect(css).toMatch(/\[data-nav-chip\]::before \{[^}]*background: var\(--app-nav-chip\);/);
        expect(css).not.toMatch(/\[data-nav-chip\][^{]*\{[^}]*\bcolor:/);
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
    ['primary', 'surface', 4.5, 'Blue text actions and icons on a card (text-app-primary)'],
    ['primary', 'canvas', 4.5, 'Text actions on the canvas'],
    ['primary', 'brand-tint', 4.5, 'Text actions on the tint (avatar letters, chips)'],
    ['primary', 'wash', 4.5, 'Text actions on a hover wash'],
    ['primary-deep', 'surface', 4.5, 'Text links on a card (text-app-primary-deep)'],
    ['primary-deep', 'canvas', 4.5, 'Text links on the canvas'],
    ['primary-deep', 'brand-tint', 4.5, 'Text links on the tint'],
    ['primary-deep', 'wash', 4.5, 'Text links on a hover wash'],
    ['control', 'surface', 3, 'Edge of a control on a card (border-app-control)'],
    ['control', 'canvas', 3, 'Edge of a control on the canvas'],
    ['primary', 'surface', 3, 'Switch face, checked box and radio dot on a card'],
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
    ['series-1', 'sunken', 3, 'Bar on its track'],
    ['viz-neutral', 'surface', 3, 'The mark of an answer that has no series of its own'],
    ['viz-neutral', 'sunken', 3, 'That mark on its track']
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

// ------------------------------------------------------------------------------------------ colour-blind reading

// The simulation, the thresholds and their method are shared with Daybreak's test (test/colour-vision.ts).

describe('the Pigment series can be told apart without colour, and none reads as a warning', () => {
    const series = (theme: Theme, count: number) => Array.from({ length: count }, (_, i) => role(theme, `series-${i + 1}`));
    const names = ['iris', 'deep green', 'ochre', 'orchid', 'warm dark neutral', 'teal'];

    it('has no red, and keeps every series a clear distance from the danger colour in hue and in colour', () => {
        const bad = role('pigment', 'bad');
        series('pigment', 6).forEach((colour, index) => {
            const { saturation } = hueAndSaturation(colour);
            expect(deltaE(colour, bad), `${names[index]} ${colour} against bad ${bad}`).toBeGreaterThanOrEqual(DANGER_DELTA_E);
            if (saturation >= 0.2) expect(hueDistance(colour, bad), `${names[index]} hue`).toBeGreaterThanOrEqual(DANGER_HUE);
        });
        // the tomato and coral pigments are identity colours, never a series
        for (const pigment of ['tomato']) expect(series('pigment', 6)).not.toContain(colour('pigment', `--app-pig-${pigment}`));
        expect(series('pigment', 6)).not.toContain(role('pigment', 'attention'));
    });

    it('gives neighbouring series different lightness, not only a different hue (series 1 to 5, one per answer)', () => {
        const five = series('pigment', 5);
        for (let i = 0; i + 1 < five.length; i++) expect(contrast(five[i], five[i + 1]), `series ${i + 1} and ${i + 2}`).toBeGreaterThanOrEqual(NEIGHBOUR_LUMINANCE);
        for (let i = 0; i + 2 < five.length; i++) expect(contrast(five[i], five[i + 2]), `series ${i + 1} and ${i + 3}`).toBeGreaterThanOrEqual(SECOND_NEIGHBOUR_LUMINANCE);
        // the sixth, used only by the sixth slice of a donut, still differs from the fifth in lightness
        expect(contrast(role('pigment', 'series-5'), role('pigment', 'series-6'))).toBeGreaterThanOrEqual(NEIGHBOUR_LUMINANCE);
    });

    it.each([
        ['deuteranopia', DEUTERANOPIA],
        ['protanopia', PROTANOPIA]
    ])('keeps series 1 to 5 apart for %s (CIE76 ΔE at least 40 between neighbours and second neighbours)', (_, matrix) => {
        const five = series('pigment', 5);
        for (let i = 0; i + 1 < five.length; i++) expect(deltaE(five[i], five[i + 1], matrix), `series ${i + 1} and ${i + 2}`).toBeGreaterThanOrEqual(SIMULATED_DELTA_E);
        for (let i = 0; i + 2 < five.length; i++) expect(deltaE(five[i], five[i + 2], matrix), `series ${i + 1} and ${i + 3}`).toBeGreaterThanOrEqual(SIMULATED_DELTA_E);
    });

    it.each([
        ['deuteranopia', DEUTERANOPIA],
        ['protanopia', PROTANOPIA]
    ])('keeps the sixth series from the fifth for %s (ΔE at least 25: the sixth slice of a donut also has a pattern and a label)', (_, matrix) => {
        expect(deltaE(role('pigment', 'series-5'), role('pigment', 'series-6'), matrix)).toBeGreaterThanOrEqual(25);
    });

    it('draws every series at least 3:1 on a white card, and series 1 to 5 on a bar track too, so a bar is not only told by colour', () => {
        series('pigment', 6).forEach((colour, index) => expect(contrast(colour, role('pigment', 'surface')), names[index]).toBeGreaterThanOrEqual(3));
        series('pigment', 5).forEach((colour, index) => expect(contrast(colour, role('pigment', 'sunken')), `${names[index]} on the track`).toBeGreaterThanOrEqual(3));
    });

    it('keeps the neutral of an answer that has no series apart from series 1 to 5, for normal vision and for both kinds of colour blindness', () => {
        const neutral = role('pigment', 'viz-neutral');
        series('pigment', 5).forEach((colour, index) => {
            expect(deltaE(neutral, colour), names[index]).toBeGreaterThanOrEqual(30);
            for (const matrix of [DEUTERANOPIA, PROTANOPIA]) expect(deltaE(neutral, colour, matrix), `${names[index]} simulated`).toBeGreaterThanOrEqual(20);
        });
        // it is never a red either
        expect(deltaE(neutral, role('pigment', 'bad'))).toBeGreaterThanOrEqual(DANGER_DELTA_E);
    });

    it('simulates a known pair correctly (the old red and green of Pigment are confusable, iris and ochre are not)', () => {
        expect(deltaE('#D44A33', '#0E8C6A', DEUTERANOPIA)).toBeLessThan(60);
        expect(deltaE('#4B35DB', '#AD6E00', DEUTERANOPIA)).toBeGreaterThan(100);
        expect(deltaE('#FFFFFF', '#FFFFFF', DEUTERANOPIA)).toBeLessThan(0.5);
    });
});

describe('Daybreak\'s six series, held to the same simulation', () => {
    const daybreak = Array.from({ length: 6 }, (_, i) => role('daybreak', `series-${i + 1}`));

    it('are each at least 3:1 on a white card', () => {
        daybreak.forEach((colour) => expect(contrast(colour, role('daybreak', 'surface'))).toBeGreaterThanOrEqual(3));
    });

    it('keep series 2 and 4 apart for deuteranopia', () => {
        expect(deltaE(daybreak[1], daybreak[3], DEUTERANOPIA)).toBeGreaterThanOrEqual(SIMULATED_DELTA_E);
    });

    it('keep every series a clear distance from the danger colour', () => {
        const bad = role('daybreak', 'bad');
        daybreak.forEach((colour) => expect(deltaE(colour, bad)).toBeGreaterThanOrEqual(DANGER_DELTA_E));
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

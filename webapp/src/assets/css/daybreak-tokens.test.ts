import { readFileSync, readdirSync, statSync } from 'fs';
import { join, resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { PIGMENTS } from '@app/lib/form-hue';
import { contrast } from '@app/utils/color-contrast';

// The Daybreak roles in DESIGN.md §1, held to the stylesheet that implements them.
const css = readFileSync(resolve(__dirname, 'tailwind.css'), 'utf8');
const globals = readFileSync(resolve(__dirname, 'globals.css'), 'utf8');
const SRC = resolve(__dirname, '../..');

/** The Daybreak scope (the default app theme): its `--app-*` and `--series-*` variables. */
const scope = css.match(/^\[data-app-theme='daybreak'\] \{([^}]*)\}/m)?.[1] ?? '';
/** The same variables on `<html>`, in a rule of their own (a browser without `:has` drops only that rule). */
const mirror = css.match(/^html:has\(\[data-app-theme='daybreak'\]\) \{([^}]*)\}/m)?.[1] ?? '';
/** The `@theme inline` block: the utilities' colour names mapped to those variables. */
const inline = css.match(/@theme inline \{([^}]*)\}/)?.[1] ?? '';
const variableOf = (name: string) => (name.startsWith('series-') ? `--series-${name.slice(7)}` : name.startsWith('form-hue-') ? `--${name}` : `--app-${name}`);

/** The value of a role: a variable of the Daybreak scope (or a ramp token in `@theme`), with `var()` aliases followed. */
function colour(name: string, fromTheme = false): string {
    // `fromTheme`: the name is a ramp or `action` token of `@theme` (a scope variable can share its name, as `--app-action` does)
    const raw = ((fromTheme ? null : scope.match(new RegExp(`${variableOf(name)}:\\s*([^;]+);`))) ?? css.match(new RegExp(`--color-${name}:\\s*([^;]+);`)))?.[1].replace(/\/\*.*$/, '').trim();
    if (!raw) throw new Error(`no token ${name}`);
    const alias = raw.match(/^var\(--(color|app)-([\w-]+)\)$/);
    return (alias ? colour(alias[2], alias[1] === 'color') : raw).toUpperCase();
}

const DAYBREAK: Record<string, string> = {
    canvas: '#F3F6FF',
    surface: '#FFFFFF',
    sunken: '#E8EDFF',
    hairline: '#DCE2F5',
    'hairline-strong': '#BDC8E8',
    'control-edge': '#6E7CA8',
    ink: '#0E1737',
    copy: '#3C4872',
    'ink-muted': '#56628C',
    sun: '#FFB400',
    'sun-tint': '#FFF1C7',
    'sun-ink': '#6B4700',
    coral: '#FF6A48',
    'coral-tint': '#FFE4DC',
    'coral-ink': '#A22F14',
    ok: '#0A6F45',
    'ok-fill': '#12A06A',
    'ok-tint': '#DDF5EA',
    warn: '#7A4B00',
    'warn-fill': '#F5A300',
    'warn-tint': '#FFF1D1',
    bad: '#B42B2B',
    'bad-fill': '#D64545',
    'bad-tint': '#FDE6E6',
    info: '#1035A8',
    'info-fill': '#3B6BFF',
    'info-tint': '#E0E8FF',
    'series-1': '#2A55E0',
    'series-2': '#A86400',
    'series-3': '#0E7F86',
    'series-4': '#C93A21',
    'series-5': '#7447CF',
    'series-6': '#5C6788'
};

describe('Daybreak tokens', () => {
    it.each(Object.entries(DAYBREAK))('--color-%s is %s', (name, hex) => {
        expect(colour(name)).toBe(hex);
    });

    it.each(Object.keys(DAYBREAK))('the utility colour %s reads its theme variable', (name) => {
        expect(inline).toContain(`--color-${name}: var(${variableOf(name)});`);
    });

    it('keeps the values in the scope, not in @theme, so a later theme only overrides variables', () => {
        expect(scope).not.toBe('');
        expect(css).not.toMatch(/--color-(canvas|surface|sunken|ink|copy|sun|coral|ok|warn|bad|info|series-1):\s*#/);
    });

    it('declares the theme variables only inside a [data-app-theme=...] rule, never globally', () => {
        // Every `--app-*`, `--series-*` and `--form-hue-*` declaration in the stylesheets sits in a rule whose selector names the
        // theme attribute: a declaration at `:root` or in `@theme` would reach respondent routes.
        for (const [file, source] of [
            ['tailwind.css', css],
            ['globals.css', globals]
        ]) {
            const text = source.replace(/\/\*[\s\S]*?\*\//g, '');
            if (file === 'tailwind.css') expect([...text.matchAll(/(--(?:app|series|form-hue)-[\w-]+)\s*:/g)].length).toBeGreaterThan(60);
            for (const declared of text.matchAll(/(--(?:app|series|form-hue)-[\w-]+)\s*:/g)) {
                // the selector of the innermost rule around this declaration
                let depth = 0;
                let open = -1;
                for (let i = declared.index! - 1; i >= 0; i--) {
                    if (text[i] === '}') depth++;
                    else if (text[i] === '{') {
                        if (depth === 0) {
                            open = i;
                            break;
                        }
                        depth--;
                    }
                }
                const start = Math.max(text.lastIndexOf('}', open), text.lastIndexOf(';', open), text.lastIndexOf('{', open - 1)) + 1;
                const selector = text.slice(start, open).trim();
                expect(selector, `${file}: ${declared[1]}`).toContain('[data-app-theme=');
            }
        }
    });

    it('puts the html mirror in its own rule, identical to the scoped one, so a browser without :has loses only the mirror', () => {
        expect(css).not.toMatch(/\[data-app-theme='daybreak'\],\s*html:has/);
        expect(scope).not.toBe('');
        expect(mirror).toBe(scope);
    });

    it('lets no theme block redeclare the frozen brand and black ramps', () => {
        // Respondent routes, the trust strip and the "Powered by" badge read `--color-brand-*` and `--color-black-*`
        // from `@theme`; an app theme only sets `--app-*` and `--series-*`. (Referring to a ramp, as the
        // `brand-tint` alias does, is fine; declaring one is not.)
        const blocks = [...css.matchAll(/\[data-app-theme=[^{]*\{([^}]*)\}/g)].map((match) => match[1]);
        expect(blocks.length).toBeGreaterThan(0);
        for (const block of blocks) {
            expect(block).not.toMatch(/--color-(brand|black)[\w-]*\s*:/);
            for (const declared of block.matchAll(/(--[\w-]+)\s*:/g)) expect(declared[1]).toMatch(/^--(app|series|form-hue)-/);
        }
    });

    it('names the brand roles that already exist, without copying them', () => {
        expect(scope).toMatch(/--app-brand-tint:\s*var\(--color-brand-100\)/);
        expect(scope).toMatch(/--app-link:\s*var\(--color-brand-600\)/);
        expect(colour('brand-tint')).toBe('#E0E8FF');
        expect(colour('link')).toBe('#1035A8');
    });

    it('leaves the blue action colour and both ramps as they were', () => {
        expect(colour('action')).toBe('#1649E2');
        expect(colour('action-hover')).toBe('#123FC9');
        expect(colour('action-pressed')).toBe('#0E2D8F');
        expect(colour('brand-500')).toBe('#123FC9');
        expect(colour('black-100')).toBe('#F5F7FB');
        expect(colour('black-900')).toBe('#101828');
        expect(colour('body')).toBe('#5A6478');
        expect(colour('control')).toBe('#818CA0');
    });

    it('does not take names shadcn components already use', () => {
        // `bg-muted`, `bg-accent` and `text-muted-foreground` sit in shadcn components; defining
        // those tokens would paint them.
        for (const reserved of ['muted', 'accent', 'primary', 'secondary', 'destructive', 'background', 'foreground', 'border', 'input', 'ring', 'card', 'popover']) {
            expect(css).not.toMatch(new RegExp(`--color-${reserved}:`));
        }
    });
});

/** [foreground, background, needs, what it is]. Text 4.5, controls, edges and chart marks 3. */
const PAIRS: Array<[string, string, number, string]> = [
    ['ink', 'canvas', 4.5, 'Headings and answers on the canvas'],
    ['ink', 'surface', 4.5, 'Headings and answers on a card'],
    ['copy', 'canvas', 4.5, 'Running text on the canvas'],
    ['copy', 'surface', 4.5, 'Running text on a card, inactive nav item'],
    ['ink-muted', 'canvas', 4.5, 'Labels and captions on the canvas'],
    ['ink-muted', 'surface', 4.5, 'Labels, captions and inactive nav icons on a card'],
    ['ink-muted', 'sunken', 4.5, 'Neutral status pill text'],
    ['link', 'surface', 4.5, 'Links, count on the active nav item'],
    ['link', 'brand-tint', 4.5, 'Active nav item: blue text on the blue tint'],
    ['ink', 'brand-tint', 4.5, 'Selected option label'],
    ['action', 'surface', 3, 'Selected option edge on a card'],
    ['brand-500', 'surface', 3, 'Focus ring (Sireto blue, the real ring colour) on a card'],
    ['brand-500', 'canvas', 3, 'Focus ring on the canvas'],
    ['action', 'brand-tint', 3, 'Selected option edge on its tint'],
    ['link', 'brand-tint', 3, 'Check mark on a selected option'],
    ['control-edge', 'surface', 3, 'Control edge on a card'],
    ['control-edge', 'canvas', 3, 'Control edge on the canvas'],
    ['sun-ink', 'sun-tint', 4.5, 'Sun text on its tint'],
    ['coral-ink', 'coral-tint', 4.5, 'Coral text on its tint'],
    ['ink', 'sun-tint', 4.5, 'Ink on the sun tint'],
    ['ink', 'coral-tint', 4.5, 'Ink on the coral tint'],
    ['ok', 'ok-tint', 4.5, 'Success pill'],
    ['warn', 'warn-tint', 4.5, 'Warning pill'],
    ['bad', 'bad-tint', 4.5, 'Danger pill'],
    ['info', 'info-tint', 4.5, 'Info pill'],
    ['ok', 'surface', 4.5, 'Success text on a card'],
    ['warn', 'surface', 4.5, 'Warning text on a card ("why we ask" missing)'],
    ['bad', 'surface', 4.5, 'Danger text on a card'],
    ['bad', 'canvas', 4.5, 'Required asterisk and error text on the canvas'],
    ['ok-fill', 'surface', 3, 'Success icon on a card'],
    ['bad-fill', 'surface', 3, 'Danger icon on a card'],
    ['series-1', 'surface', 3, 'Chart series 1 (blue)'],
    ['series-2', 'surface', 3, 'Chart series 2 (ochre)'],
    ['series-3', 'surface', 3, 'Chart series 3 (teal)'],
    ['series-4', 'surface', 3, 'Chart series 4 (red-orange)'],
    ['series-5', 'surface', 3, 'Chart series 5 (violet)'],
    ['series-6', 'surface', 3, 'Chart series 6 (slate)'],
    ['series-1', 'sunken', 3, 'Bar on its track'],
    ['copy', 'brand-tint', 4.5, 'Welcome band and empty-state panel text'],
    ['ink', 'brand-tint', 4.5, 'Welcome band greeting'],
    ['copy', 'surface', 4.5, 'Empty-state sentence on its white card'],
    ['ink', 'surface', 4.5, 'Empty-state title on its white card'],
    ['coral-ink', 'coral-tint', 4.5, 'Count badge: the number on coral tint'],
    ['form-hue-0-ink', 'form-hue-0-bg', 4.5, 'Form tile 0 (coral pair)'],
    ['form-hue-1-ink', 'form-hue-1-bg', 4.5, 'Form tile 1 (sun pair)'],
    ['form-hue-2-ink', 'form-hue-2-bg', 4.5, 'Form tile 2 (success pair)'],
    ['form-hue-3-ink', 'form-hue-3-bg', 4.5, 'Form tile 3 (blue pair)'],
    ['form-hue-4-ink', 'form-hue-4-bg', 4.5, 'Form tile 4 (violet pair)']
];

describe('form tile pairs', () => {
    it.each([0, 1, 2, 3, 4])('hue %i has a tint and an ink in the scope and a utility for each', (n) => {
        expect(scope).toMatch(new RegExp(`--form-hue-${n}-bg:`));
        expect(scope).toMatch(new RegExp(`--form-hue-${n}-ink:`));
        expect(inline).toContain(`--color-form-hue-${n}-bg: var(--form-hue-${n}-bg);`);
        expect(inline).toContain(`--color-form-hue-${n}-ink: var(--form-hue-${n}-ink);`);
    });

    it('has exactly as many pairs as the hash has indexes', () => {
        expect([...scope.matchAll(/--form-hue-(\d+)-bg:/g)].length).toBe(PIGMENTS.length);
    });
});

describe('Daybreak contrast', () => {
    it.each(PAIRS)('%s on %s is at least %s:1 (%s)', (fg, bg, needs) => {
        expect(contrast(colour(fg), colour(bg))).toBeGreaterThanOrEqual(needs);
    });
});

describe('where colour goes', () => {
    const files = (dir: string, out: string[] = []): string[] => {
        for (const entry of readdirSync(dir)) {
            const path = join(dir, entry);
            if (statSync(path).isDirectory()) files(path, out);
            else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) out.push(path);
        }
        return out;
    };

    it('puts the app canvas on the body inside the scope, and paper mist everywhere else', () => {
        expect(css).toMatch(/html,\s*body \{[^}]*background-color: var\(--app-canvas, var\(--color-black-100\)\);/);
        expect(globals).toMatch(/body \{\s*background: var\(--app-canvas, var\(--color-black-100\)\);/);
    });

    it('sets the theme attribute on the creator app layouts only, never on a respondent route', () => {
        const read = (path: string) => readFileSync(resolve(SRC, path), 'utf8');
        expect(read('app/(admin-portal)/layout.tsx')).toMatch(/data-app-theme="daybreak"/);
        // sign-in: the creator's only (the respondent's, `?type=responder`, is a respondent route)
        expect(read('app/(auth)/_components/login-view.tsx')).toMatch(/data-app-theme=\{isResponder \? undefined : 'daybreak'\}/);
        const carriers = files(SRC)
            .filter((path) => /data-app-theme/.test(readFileSync(path, 'utf8')))
            .map((path) => path.slice(SRC.length + 1))
            .sort();
        // the workspace's own theme (Daybreak or Pigment, from its setting) is placed by one component, used by the
        // workspace layout of the admin portal and nowhere else
        expect(carriers).toEqual(['app/(admin-portal)/layout.tsx', 'app/(auth)/_components/login-view.tsx', 'components/app-theme/app-theme-scope.tsx']);
        const users = files(SRC)
            .filter((path) => /app-theme-scope/.test(readFileSync(path, 'utf8')))
            .map((path) => path.slice(SRC.length + 1))
            .sort();
        expect(users).toEqual(['app/(admin-portal)/(no-layout)/[workspace_name]/layout.tsx']);
    });

    it('writes the value as daybreak on the creator layouts, and as the workspace\'s own daybreak or pigment in the one scope component', () => {
        // a literal value anywhere is `daybreak` (the creator layouts); the workspace's is a variable, one of two
        const values = new Set(files(SRC).flatMap((path) => [...readFileSync(path, 'utf8').matchAll(/data-app-theme=["']([a-z]+)["']/g)].map((match) => match[1])));
        expect([...values].sort()).toEqual(['daybreak']);
        const scopeSource = readFileSync(resolve(SRC, 'components/app-theme/app-theme-scope.tsx'), 'utf8');
        expect(scopeSource).toMatch(/data-app-theme=\{theme\}/);
        expect(readFileSync(resolve(SRC, 'lib/app-theme.ts'), 'utf8')).toMatch(/APP_THEMES = \['daybreak', 'pigment'\] as const/);
    });

    it('never gives sun or coral to a button; the primary stays blue', () => {
        const button = readFileSync(resolve(SRC, 'shadcn/components/ui/button.tsx'), 'utf8');
        expect(button).not.toMatch(/\b(sun|coral)\b/);
        expect(button).toMatch(/bg-app-action/);
        const offenders = files(SRC).filter((path) => {
            const text = readFileSync(path, 'utf8');
            // a `<button>` or `<Button>` whose own class list takes a sun or coral fill
            return /<(?:button|Button)\b[^>]*className=["'`{][^>]*\bbg-(?:sun|coral)\b/.test(text);
        });
        expect(offenders).toEqual([]);
    });

    it('draws report series from the tokens, light only, with no hard-coded hue', () => {
        const block = globals.match(/\.report-viz \{([^}]*)\}/)?.[1] ?? '';
        // the series are variables of the theme scope (`--series-1..6`), so a later theme only overrides them
        for (const n of [1, 2, 3, 4, 5, 6]) expect(scope).toMatch(new RegExp(`--series-${n}:\\s*#[0-9A-F]{6};`));
        expect(block).not.toMatch(/#[0-9a-f]{3,6}/i);
        expect(block).not.toContain('--series-');
        // no dark step: the app has no dark theme and the report cards are always white
        expect(globals).not.toMatch(/prefers-color-scheme:\s*dark[^}]*\{[^}]*report-viz/s);
        expect(globals).not.toMatch(/data-theme='dark'\] \.report-viz/);
    });
});

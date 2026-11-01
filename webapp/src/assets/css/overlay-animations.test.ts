// @vitest-environment node
import { readFileSync, readdirSync } from 'fs';
import { join, resolve } from 'path';

import { execFileSync } from 'child_process';
import { beforeAll, describe, expect, it } from 'vitest';

/**
 * The shadcn components animate their enter and exit with `animate-in`,
 * `fade-in-0`, `zoom-in-95`, `slide-in-from-*` and friends. Tailwind 4 has no
 * such utilities of its own (tailwindcss-animate is retired); `tw-animate-css`
 * provides them, imported in tailwind.css. Held here against the stylesheet as
 * Tailwind builds it, so the classes cannot silently turn into no-ops again.
 */

const CSS_DIR = __dirname;
const UI_DIR = resolve(__dirname, '../../shadcn/components/ui');

/** Every enter/exit animation class (with or without variants) the shadcn components use. */
function animationClasses(): string[] {
    const found = new Set<string>();
    for (const file of readdirSync(UI_DIR).filter((name) => name.endsWith('.tsx'))) {
        const text = readFileSync(join(UI_DIR, file), 'utf8');
        for (const token of text.match(/[^\s"'`]+/g) ?? []) {
            if (/(^|:)(animate-(in|out)|fade-(in|out)(-\d+)?|zoom-(in|out)(-\d+)?|slide-(in-from|out-to)-[a-z]+(-[\w[\]%.]+)?)$/.test(token)) found.add(token);
        }
    }
    return [...found].sort();
}

/**
 * The stylesheet as Tailwind builds it for some classes. Tailwind's compiler
 * cannot be loaded inside Vitest (it registers Node module hooks), so a child
 * Node process runs it and prints the CSS.
 */
function build(classes: string[], css: string): string {
    const script = `
        import { compile } from '@tailwindcss/node';
        const [base, source, classes] = JSON.parse(process.argv[1]);
        const compiler = await compile(source, { base, onDependency() {} });
        process.stdout.write(compiler.build(classes));
    `;
    return execFileSync(process.execPath, ['--input-type=module', '-e', script, JSON.stringify([CSS_DIR, css, classes])], { cwd: resolve(__dirname, '../../..'), encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
}

let built = '';
let source = '';

beforeAll(() => {
    source = readFileSync(join(CSS_DIR, 'tailwind.css'), 'utf8');
    built = build(animationClasses(), source);
}, 60_000);

/** A class name as it is written in a selector. */
const escaped = (name: string) => '.' + name.replace(/([^\w-])/g, '\\$1');

describe('overlay animations', () => {
    it('finds the animation classes the shadcn components use', () => {
        const classes = animationClasses();
        expect(classes.length).toBeGreaterThan(15);
        expect(classes).toContain('data-[state=open]:animate-in');
        expect(classes).toContain('data-[state=closed]:fade-out-0');
        expect(classes.some((name) => name.includes('slide-in-from-'))).toBe(true);
    });

    it('generates a rule for every one of them', () => {
        const missing = animationClasses().filter((name) => !built.includes(escaped(name)));
        expect(missing).toEqual([]);
    });

    it('animates with the enter and exit keyframes', () => {
        expect(built).toMatch(/@keyframes enter\b/);
        expect(built).toMatch(/@keyframes exit\b/);
        expect(built).toMatch(/animation: enter /);
        expect(built).toMatch(/animation: exit /);
    });

    it('has a unit for the slide distances (`slide-in-from-top-2` is two steps of it)', () => {
        expect(built).toMatch(/--tw-enter-translate-y: calc\(2\*var\(--spacing\)\*-1\)/);
        expect(built).toMatch(/:root\s*\{[^}]*--spacing: 0\.25rem/);
    });

    it('does not turn that unit into spacing utilities (the theme keeps its closed scale)', () => {
        expect(build(['p-34'], source)).not.toContain('.p-34');
    });

    it('switches the animation off for people who ask for reduced motion', () => {
        const block = built.match(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\[class\*=["']animate-in["']\],\s*\[class\*=["']animate-out["']\]\s*\{([^}]*)\}/);
        expect(block, 'a reduced-motion rule for animate-in / animate-out').not.toBeNull();
        expect(block![1]).toMatch(/animation:\s*none\s*!important/);
    });
});

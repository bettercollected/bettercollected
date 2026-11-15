// A small model of the custom-property cascade for tests: jsdom does not compute `var()`, so a test that asks "what
// colour does this button draw inside a Pigment scope" resolves the stylesheet's own expressions here, the way a browser
// does: inline custom properties of the ancestors (`initial` makes a property guaranteed-invalid, so the `var()`
// fallback applies), then the app theme scope and its `<html>` mirror from tailwind.css, then the `@theme` tokens.
import { readFileSync } from 'fs';
import { resolve as resolvePath } from 'path';

export const CSS_FILE = readFileSync(resolvePath(__dirname, '../assets/css/tailwind.css'), 'utf8');

/** The variables a rule of tailwind.css declares: variable to raw value. */
export function declarationsOf(selectorPattern: string): Record<string, string> {
    const body = CSS_FILE.match(new RegExp(`^${selectorPattern} \\{([^}]*)\\}`, 'm'))?.[1] ?? '';
    const out: Record<string, string> = {};
    for (const line of body.replace(/\/\*[\s\S]*?\*\//g, '').split(';')) {
        const match = line.match(/^\s*(--[\w-]+)\s*:\s*([\s\S]+?)\s*$/);
        if (match) out[match[1]] = match[2];
    }
    return out;
}

export const scopeRule = (theme: string) => declarationsOf(`\\[data-app-theme='${theme}'\\]`);
export const htmlRule = (theme: string) => declarationsOf(`html:has\\(\\[data-app-theme='${theme}'\\]\\)`);

/** The expression a `@theme` entry (a utility's colour, a ramp step) stands for: `--color-app-action` and so on. */
export const themeEntry = (name: string): string | undefined =>
    CSS_FILE.match(new RegExp(`${name}:\\s*([^;]+);`))?.[1]
        .replace(/\/\*.*$/, '')
        .trim();

/** The text inside `var(` ... `)` starting at `start` (just after the open parenthesis), and the index after the close. */
function balanced(text: string, start: number): [string, number] {
    let depth = 1;
    let i = start;
    for (; i < text.length && depth > 0; i++) {
        if (text[i] === '(') depth++;
        else if (text[i] === ')') depth--;
    }
    return [text.slice(start, i - 1), i];
}

function lookup(node: Element | null, name: string): string | undefined {
    for (let el: Element | null = node; el; el = el.parentElement) {
        const inline = (el as HTMLElement).style?.getPropertyValue(name);
        if (inline) return inline === 'initial' ? undefined : resolveValue(inline, el);
        const theme = el.getAttribute?.('data-app-theme');
        if (theme && scopeRule(theme)[name] !== undefined) return resolveValue(scopeRule(theme)[name], el);
    }
    // `<html>` carries the mirror of the theme a page uses (so portals read it too)
    const used = node?.ownerDocument.querySelector('[data-app-theme]')?.getAttribute('data-app-theme');
    if (used && htmlRule(used)[name] !== undefined) return resolveValue(htmlRule(used)[name], node!.ownerDocument.documentElement);
    const token = name.startsWith('--color-') ? themeEntry(name) : undefined;
    // a `@theme inline` entry is written into the utility, so its `var()`s resolve at the element that uses it
    return token === undefined ? undefined : resolveValue(token, node);
}

/** `value` with every `var(--x, fallback)` resolved at `node`; a variable that is unset takes its fallback. */
export function resolveValue(value: string, node: Element | null): string {
    let out = '';
    let i = 0;
    while (i < value.length) {
        const at = value.indexOf('var(', i);
        if (at < 0) return out + value.slice(i);
        out += value.slice(i, at);
        const [inner, next] = balanced(value, at + 4);
        const comma = inner.indexOf(',');
        const name = (comma < 0 ? inner : inner.slice(0, comma)).trim();
        const fallback = comma < 0 ? undefined : inner.slice(comma + 1).trim();
        const found = lookup(node, name);
        out += found ?? (fallback === undefined ? '' : resolveValue(fallback, node));
        i = next;
    }
    return out;
}

/** What an element draws for a utility's colour: `colourAt(button, '--color-app-action')`, upper case. */
export function colourAt(node: Element, entry: string): string {
    return resolveValue(`var(${entry})`, node).toUpperCase();
}

import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { resolveValue, scopeRule } from '@app/test/app-theme-cascade';

import { TABLE_EDGE, TABLE_EDGE_STRONG, TABLE_WASH, dataTableCustomStyles, deletionRequestTableStyles, simpleDataTableStyles } from './datatable-styles';

// The admin tables take their edges and header band from the app theme's roles, with the frozen value as the fallback:
// Daybreak (where each role is exactly that value) and a page with no scope draw what they always drew, and a table in a
// Pigment workspace is warm. No literal colour is left in the shared style objects.

const strings = (value: unknown): string[] => (typeof value === 'string' ? [value] : value && typeof value === 'object' ? Object.values(value).flatMap(strings) : []);
// `var(--name, <fallback>)` is the way a frozen value is written; it is cut out before a literal colour is looked for
const withoutFallbacks = (text: string) => text.replace(/var\(--[\w-]+,\s*#[0-9a-fA-F]{3,8}\)/g, 'var()');
const LITERAL_COLOUR = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/;

describe('the shared table styles', () => {
    it.each([
        ['dataTableCustomStyles', dataTableCustomStyles],
        ['deletionRequestTableStyles', deletionRequestTableStyles]
    ])('%s holds no literal colour', (_name, styles) => {
        const literals = strings(styles)
            .map(withoutFallbacks)
            .filter((text) => LITERAL_COLOUR.test(text));
        expect(literals).toEqual([]);
    });

    it('draws the header band, the outer edges and the cell lines from the wash and the edge roles', () => {
        expect(dataTableCustomStyles.headRow.style.backgroundColor).toBe(TABLE_WASH);
        expect(dataTableCustomStyles.table.style.borderTop).toBe(`1px solid ${TABLE_EDGE_STRONG}`);
        expect(dataTableCustomStyles.cells.style.borderRight).toBe(`1px solid ${TABLE_EDGE}`);
        expect(dataTableCustomStyles.headCells.style.borderRight).toBe(`1px solid ${TABLE_EDGE}`);
        expect(simpleDataTableStyles.headRow.style.backgroundColor).toBe(TABLE_WASH);
    });

    it('has fallbacks that are exactly the Daybreak values of the roles, so Daybreak and a page with no scope are unchanged', () => {
        const daybreak = (role: string) => resolveValue(scopeRule('daybreak')[role], document.body).toUpperCase();
        const fallback = (value: string) => value.match(/#[0-9A-Fa-f]{6}/)![0].toUpperCase();
        expect(fallback(TABLE_WASH)).toBe(daybreak('--app-wash'));
        expect(fallback(TABLE_EDGE)).toBe(daybreak('--app-edge'));
        expect(fallback(TABLE_EDGE_STRONG)).toBe(daybreak('--app-edge-strong'));
    });

    it('reads the Pigment values inside a Pigment scope, and the frozen ones with no scope', () => {
        const scope = document.createElement('div');
        scope.setAttribute('data-app-theme', 'pigment');
        document.body.appendChild(scope);
        const bare = document.createElement('div');
        document.body.appendChild(bare);
        const html = document.documentElement;
        for (const value of [TABLE_WASH, TABLE_EDGE, TABLE_EDGE_STRONG]) {
            expect(resolveValue(value, scope).toUpperCase(), value).not.toBe(value.match(/#[0-9A-Fa-f]{6}/)![0].toUpperCase());
        }
        scope.remove();
        // with no scope anywhere in the document the fallback applies
        expect(resolveValue(TABLE_WASH, bare).toUpperCase()).toBe('#F5F7FB');
        expect(resolveValue(TABLE_EDGE, bare).toUpperCase()).toBe('#EAECF0');
        expect(resolveValue(TABLE_EDGE_STRONG, bare).toUpperCase()).toBe('#D0D5DD');
        bare.remove();
        expect(html).toBeTruthy();
    });

    it('leaves in the custom-domain table only its old pure greys, which are neither a role nor a ramp step', () => {
        const literals = strings(simpleDataTableStyles)
            .map(withoutFallbacks)
            .flatMap((text) => text.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []);
        expect([...new Set(literals)].sort()).toEqual(['#2E2E2E', '#4D4D4D', '#6E6E6E', '#F6F6F6']);
    });

    it('keeps the response and deletion tables off literal colours too', () => {
        const source = readFileSync(resolve(__dirname, 'responses-table.tsx'), 'utf8');
        expect(source.match(/#[0-9a-fA-F]{6}\b/g) ?? []).toEqual([]);
    });
});

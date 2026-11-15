import React from 'react';

import { readFileSync } from 'fs';
import { resolve } from 'path';

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { FORM_CARD, FORM_ROWS } from '@app/components/form/form-page';

import { PAGE_CARD, PAGE_ROWS, PageSurface } from './page-surface';

// The creator app's pages sit on the periwinkle canvas, so what was laid out for a white page sits on one surface
// pattern: the form pages and the workspace pages share it (components/ui/page-surface.tsx).
describe('the page surface', () => {
    it('is a white card with the strong hairline, a radius, 16 px inside and 24 px from sm, and uses semantic colours only', () => {
        expect(PAGE_CARD).toBe('rounded-lg border border-hairline-strong bg-surface p-4 sm:p-6');
        expect(PAGE_ROWS).toContain('divide-hairline-strong');
        expect(`${PAGE_CARD} ${PAGE_ROWS}`).not.toMatch(/#[0-9a-fA-F]{3,8}|-(?:50|100|200|300|400|500|600|700|800|900)\b/);
    });

    it('is one pattern: the form pages read the same classes', () => {
        expect(FORM_CARD).toBe(PAGE_CARD);
        expect(FORM_ROWS).toBe(PAGE_ROWS);
    });

    it('holds a page of content, full width by default and in a 760 px column when narrow', () => {
        render(
            <>
                <PageSurface>
                    <p>wide page</p>
                </PageSurface>
                <PageSurface narrow>
                    <p>settings page</p>
                </PageSurface>
            </>
        );
        const wide = screen.getByText('wide page').parentElement!;
        const narrow = screen.getByText('settings page').parentElement!;
        for (const surface of [wide, narrow]) {
            expect(surface.className).toContain('bg-surface');
            expect(surface.className).toContain('border-hairline-strong');
            expect(surface.className).toContain('w-full');
            expect(surface.className).toContain('min-w-0');
        }
        expect(wide.className).not.toContain('max-w-[760px]');
        expect(narrow.className).toContain('max-w-[760px]');
    });
});

// The pages under the workspace layout take their gutters from the layout and their surface from PageSurface: none adds
// an inset of its own (these had `px-5 lg:px-10` on top of the layout's gutter).
describe('the workspace pages', () => {
    const dashboard = resolve(__dirname, '../../app/(admin-portal)/(side-top-nav-layout)/[workspace_name]/dashboard');

    it.each([
        ['embedding', '../embed/embedding-settings.tsx'],
        ['spam protection', '../captcha/spam-check-settings.tsx'],
        ['themes', resolve(dashboard, 'themes/page.tsx')]
    ])('%s has no inset of its own and sits on the page surface', (_name, path) => {
        const source = readFileSync(resolve(__dirname, path), 'utf8');
        expect(source).not.toContain('lg:px-10');
        expect(source).toContain('PageSurface');
    });

    it.each(['ai/_components/ai-section-layout.tsx', 'sso/_components/sso-section-layout.tsx', 'members/_components/members-layout-client.tsx', 'responders-groups/_components/responders-groups-layout-client.tsx', 'responders-groups/[group_id]/_components/group-preview-layout-client.tsx'])('the section layout %s puts its tab content on the page surface', (file) => {
        expect(readFileSync(resolve(dashboard, file), 'utf8')).toContain('<PageSurface');
    });

    it('the layout gives the last card room below it', () => {
        expect(readFileSync(resolve(dashboard, '_components/workspace-dashboard-layout.tsx'), 'utf8')).toContain('px-5 lg:px-10 pt-10 pb-10');
    });
});

// The dashboard's Templates page: the predefined gallery shows every template
// in full, and its styling follows the section's variant, not its translated title.
import '@app/shared/hocs/i18n-provider';
import React from 'react';

import { render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import TemplatesClient from '@app/app/(admin-portal)/(side-top-nav-layout)/[workspace_name]/dashboard/templates/_components/templates-client';
import { IFormTemplateDto } from '@app/models/dtos/template';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import TemplateSection from './template-section';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/templates',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@Components/modals/contexts/bottom-sheet-modal-context', () => ({
    useBottomSheetModal: () => ({ openBottomSheetModal: vi.fn() })
}));
vi.mock('@app/store/template/api', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@app/store/template/api')>()),
    useGetTemplatesQuery: () => ({ data: [], isLoading: false })
}));

const TITLES = ['Contact form', 'Event registration', 'Customer feedback', 'Support triage', 'Lead qualification', 'Job application with screening'];

const template = (title: string, index: number): IFormTemplateDto =>
    ({
        id: `t${index}`,
        title,
        description: '',
        builderVersion: 'v2',
        welcomePage: { layout: 'SINGLE_COLUMN_NO_BACKGROUND', buttonText: 'Start' },
        theme: { primary: '#2E2E2E', secondary: '#0764EB', tertiary: '#A2C5F8', accent: '#F2F7FF' },
        fields: []
    }) as unknown as IFormTemplateDto;

const TEMPLATES = TITLES.map(template);

const wrap = (ui: React.ReactElement) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{ui}</Provider>
        </ReduxProvider>
    );

beforeAll(() => {
    store.dispatch(setAuth({ id: 'u1', roles: ['ADMIN'] }));
    store.dispatch(setWorkspace({ id: 'ws1', workspaceName: 'acme' }));
});

describe('Templates page, predefined section', () => {
    it('has no fixed height and renders every template in a wrapping grid', () => {
        wrap(<TemplatesClient predefined_templates={TEMPLATES} />);
        const section = screen.getByTestId('template-section');
        expect(section.getAttribute('data-variant')).toBe('predefined');
        expect(section.className).not.toMatch(/(^|\s)(h|max-h)-\[/);
        expect(section.className).not.toMatch(/overflow-(hidden|x-auto|y-auto)/);
        const grid = screen.getByTestId('template-grid');
        expect(grid.className).toContain('grid');
        expect(grid.className).not.toContain('overflow-x-auto');
        expect(within(grid).getAllByTestId('template-card')).toHaveLength(TITLES.length);
        for (const title of TITLES) {
            // The card title and the preview's heading.
            expect(within(grid).getAllByText(title).length).toBeGreaterThanOrEqual(2);
        }
    });

    it('lets a card title use the card width', () => {
        wrap(<TemplateSection title="Default" variant="predefined" templates={TEMPLATES} />);
        const title = screen.getAllByText('Job application with screening').find((el) => el.tagName === 'SPAN')!;
        expect(title.className).toContain('w-full');
        expect(title.className).toContain('truncate');
        expect(title.className).not.toMatch(/max-w-\[\d+px\]/);
        expect(title.getAttribute('title')).toBe('Job application with screening');
    });

    it('previews each template with its own title on the welcome page', () => {
        wrap(<TemplateSection title="Default" variant="predefined" templates={TEMPLATES} />);
        expect(screen.getByRole('heading', { level: 1, name: 'Support triage' })).toBeDefined();
        expect(screen.getAllByRole('button', { name: 'Start' })).toHaveLength(TITLES.length);
    });
});

describe('TemplateSection variant drives styling, in any language', () => {
    // English "Default" and Dutch "Standaard": the title is only a label.
    it.each(['Default', 'Standaard'])('predefined with title "%s": white band, no card menus', (title) => {
        wrap(<TemplateSection title={title} variant="predefined" templates={TEMPLATES.slice(0, 2)} />);
        const section = screen.getByTestId('template-section');
        expect(section.className).toContain('bg-white');
        expect(screen.getByRole('heading', { name: title })).toBeDefined();
        expect(screen.queryByText(/TEMPLATE.CREATED|Created/)).toBeNull();
    });

    it.each(['Your Workspace v2', 'Je Werkruimte v2', 'Default', 'Standaard'])('workspace with title "%s": no white band, card details shown', (title) => {
        wrap(<TemplateSection title={title} variant="workspace" templates={TEMPLATES.slice(0, 2)} />);
        const section = screen.getByTestId('template-section');
        expect(section.className).not.toContain('bg-white');
        expect(screen.getAllByTestId('template-card')).toHaveLength(2);
        expect(screen.getAllByText(/Created/)).toHaveLength(2);
    });
});

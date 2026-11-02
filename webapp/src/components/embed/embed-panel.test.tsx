import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import enCommon from '@app/../public/locales/en/common.json';
import ShareView from '@app/components/ui/share-view';
import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import EmbedPanel from './embed-panel';

const en = enCommon.STAFF.EMBED as any;
const URL_OF_FORM = 'https://forms.example.org/acme/forms/contact';

const perms = { enabled: true, share: true, manage: true };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ formEmbedEnabled: perms.enabled, can: (p: string) => (p === 'form.share' ? perms.share : p === 'workspace.manage' ? perms.manage : false) })
}));
vi.mock('@app/store/hooks', () => ({ useAppSelector: () => ({ id: 'ws1', workspaceName: 'acme' }) }));
vi.mock('@app/store/workspaces/slice', () => ({ selectWorkspace: () => ({}) }));
const settings: { data: any; isLoading: boolean } = { data: { origins: [] }, isLoading: false };
vi.mock('@app/store/workspaces/embed-api', () => ({ useGetEmbedSettingsQuery: () => settings }));
const copied: string[] = [];
vi.mock('@app/lib/hooks/use-copy-to-clipboard', () => ({ useCopyToClipboard: () => [null, (text: string) => copied.push(text)] }));

beforeEach(async () => {
    await i18n.changeLanguage('en');
    perms.enabled = true;
    perms.share = true;
    perms.manage = true;
    settings.data = { origins: [] };
    settings.isLoading = false;
    copied.length = 0;
});

describe('Embed panel', () => {
    it('shows the code with the form address and the script of its host, and copies it', () => {
        render(<EmbedPanel url={URL_OF_FORM} formTitle="Contact form" />);
        const code = screen.getByText(/data-bc-form=/);
        expect(code.textContent).toContain(`data-bc-form="${URL_OF_FORM}"`);
        expect(code.textContent).toContain('data-bc-title="Contact form"');
        expect(code.textContent).toContain('src="https://forms.example.org/embed/v1.js"');
        expect(code.textContent).toContain('integrity="sha384-');
        expect(code.textContent).toContain('crossorigin="anonymous"');
        fireEvent.click(screen.getByRole('button', { name: en.COPY }));
        expect(copied).toEqual([code.textContent]);
        expect(screen.getByRole('button', { name: en.COPIED })).toBeInTheDocument();
    });

    it('also offers a plain frame with no script, and copies that one on its own', () => {
        render(<EmbedPanel url={URL_OF_FORM} formTitle="Contact form" />);
        const frame = screen.getByText(/<iframe /);
        expect(frame.textContent).toContain(`src="${URL_OF_FORM}?embed=1"`);
        expect(frame.textContent).toContain('title="Contact form"');
        expect(frame.textContent).not.toContain('<script');
        expect(screen.getByText(en.IFRAME_HINT)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: en.IFRAME_COPY }));
        expect(copied).toEqual([frame.textContent]);
    });

    it('says embedding is refused until a site is added, and links admins to the settings', () => {
        render(<EmbedPanel url={URL_OF_FORM} />);
        expect(screen.getByText(en.SITES_NONE)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: en.SITES_ADD })).toHaveAttribute('href', '/acme/dashboard/embedding');
    });

    it('sends someone who cannot manage to an admin', () => {
        perms.manage = false;
        render(<EmbedPanel url={URL_OF_FORM} />);
        expect(screen.queryByRole('link')).toBeNull();
        expect(screen.getByText(en.SITES_ASK_ADMIN)).toBeInTheDocument();
    });

    it('lists the allowed sites', () => {
        settings.data = { origins: ['https://www.example.org', 'https://*.shop.example.org'] };
        render(<EmbedPanel url={URL_OF_FORM} />);
        expect(screen.getByText('https://www.example.org')).toBeInTheDocument();
        expect(screen.getByText('https://*.shop.example.org')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: en.SITES_MANAGE })).toBeInTheDocument();
        expect(screen.queryByText(en.SITES_NONE)).toBeNull();
    });

    it('has no accessibility violations', async () => {
        const view = render(<EmbedPanel url={URL_OF_FORM} formTitle="Contact form" />);
        expect(await axeViolations(view.container)).toEqual([]);
    });
});

describe('Share dialog', () => {
    it('has a Link and an Embed tab while embedding is on and the member may share', () => {
        render(<ShareView url={URL_OF_FORM} formTitle="Contact form" />);
        expect(screen.getByRole('tab', { name: en.TAB_LINK })).toHaveAttribute('aria-selected', 'true');
        fireEvent.mouseDown(screen.getByRole('tab', { name: en.TAB_EMBED }), { button: 0 });
        fireEvent.click(screen.getByRole('tab', { name: en.TAB_EMBED }));
        expect(screen.getByText(/data-bc-form=/)).toBeInTheDocument();
    });

    it('is the plain share dialog while embedding is off, or for a member who may not share', () => {
        perms.enabled = false;
        const view = render(<ShareView url={URL_OF_FORM} />);
        expect(screen.queryByRole('tab')).toBeNull();
        expect(screen.getByText(URL_OF_FORM)).toBeInTheDocument();
        view.unmount();
        perms.enabled = true;
        perms.share = false;
        render(<ShareView url={URL_OF_FORM} />);
        expect(screen.queryByRole('tab')).toBeNull();
    });
});

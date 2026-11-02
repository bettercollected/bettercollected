// The routes of a form's Settings: one address per page, the old addresses redirect, a page the form has nothing on
// redirects to Access, and focus goes to the new page's heading when the viewer moves between pages.
import React from 'react';

import { act, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';

import IntegrationsPage from '../integrations/page';
import VisibilityPage from '../visibility/page';
import SectionPage from './[section]/page';
import SettingsLayout from './layout';
import SettingsPage from './page';

// next's redirect() throws; the test reads where it was sent
class Redirected extends Error {
    constructor(public url: string) {
        super(url);
    }
}
const nav = vi.hoisted(() => ({ pathname: '/acme/dashboard/forms/f1/settings/access', section: 'access', replace: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: ['form.edit', 'form.delete'] as string[], isLoading: false }));
vi.mock('next/navigation', () => ({
    redirect: (url: string) => {
        throw new Redirected(url);
    },
    usePathname: () => nav.pathname,
    useParams: () => ({ workspace_name: 'acme', form_id: 'f1', section: nav.section }),
    useRouter: () => ({ replace: nav.replace, push: vi.fn() })
}));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (permission: string) => perms.granted.includes(permission), isLoading: perms.isLoading }) }));
vi.mock('@Components/form/settings', () => ({ default: ({ page }: { page: string }) => <h2>Page {page}</h2> }));

const params = Promise.resolve({ workspace_name: 'acme', form_id: 'f1' });
const sentTo = async (page: (props: { params: typeof params }) => Promise<unknown>) => {
    try {
        await page({ params });
    } catch (error) {
        if (error instanceof Redirected) return error.url;
        throw error;
    }
    return undefined;
};

describe('the old and the bare addresses', () => {
    it('sends /settings to Access', async () => {
        expect(await sentTo(SettingsPage)).toBe('/acme/dashboard/forms/f1/settings/access');
    });

    it('sends /visibility to Access and /integrations to Automations', async () => {
        expect(await sentTo(VisibilityPage)).toBe('/acme/dashboard/forms/f1/settings/access');
        expect(await sentTo(IntegrationsPage)).toBe('/acme/dashboard/forms/f1/settings/automations');
    });
});

describe('a Settings page', () => {
    const show = (section: string, form: Record<string, unknown> = {}) => {
        nav.section = section;
        store.dispatch(setForm({ formId: 'f1', builderVersion: 'v2', isPublished: true, settings: { provider: 'self' }, ...form } as any));
        return render(
            <ReduxProvider store={store}>
                <SectionPage />
            </ReduxProvider>
        );
    };

    beforeEach(() => {
        nav.replace.mockClear();
        perms.granted = ['form.edit', 'form.delete'];
        perms.isLoading = false;
    });

    it('shows its page', () => {
        show('availability');
        expect(screen.getByRole('heading', { name: 'Page availability' })).toBeInTheDocument();
        expect(nav.replace).not.toHaveBeenCalled();
    });

    it('sends Availability and Automations of a form imported from elsewhere to Access', () => {
        show('availability', { settings: { provider: 'google' }, builderVersion: 'v1' });
        expect(nav.replace).toHaveBeenCalledWith('/acme/dashboard/forms/f1/settings/access');
        expect(screen.queryByRole('heading')).toBeNull();
        nav.replace.mockClear();
        show('automations', { settings: { provider: 'google' }, builderVersion: 'v1' });
        expect(nav.replace).toHaveBeenCalledWith('/acme/dashboard/forms/f1/settings/access');
    });

    it('sends Advanced to Access when there is nothing on it', () => {
        perms.granted = ['form.edit'];
        show('advanced', { settings: { provider: 'google' }, builderVersion: 'v1' });
        expect(nav.replace).toHaveBeenCalledWith('/acme/dashboard/forms/f1/settings/access');
    });

    it('sends a name that is no page to Access', () => {
        show('nonsense');
        expect(nav.replace).toHaveBeenCalledWith('/acme/dashboard/forms/f1/settings/access');
    });

    it('waits for the permissions before it decides', () => {
        perms.isLoading = true;
        show('availability', { settings: { provider: 'google' }, builderVersion: 'v1' });
        expect(nav.replace).not.toHaveBeenCalled();
    });

    it('does not redirect somebody who may not edit: the page tells them itself', () => {
        perms.granted = [];
        show('availability', { settings: { provider: 'google' }, builderVersion: 'v1' });
        expect(nav.replace).not.toHaveBeenCalled();
    });
});

describe('moving between Settings pages', () => {
    const tree = () => (
        <div id="form-main">
            <SettingsLayout>
                <h2 tabIndex={-1}>Heading</h2>
            </SettingsLayout>
        </div>
    );
    const flushFrame = () => act(async () => void (await new Promise((resolve) => requestAnimationFrame(() => resolve(null)))));

    it('leaves focus alone on the first load', async () => {
        nav.pathname = '/acme/dashboard/forms/f1/settings/access';
        render(tree());
        await flushFrame();
        expect(document.activeElement).toBe(document.body);
    });

    it('waits for a heading that is not there yet (a page that loads its cards first)', async () => {
        nav.pathname = '/acme/dashboard/forms/f1/settings/access';
        const Late = ({ show }: { show: boolean }) => (
            <div id="form-main">
                <SettingsLayout>{show ? <h2 tabIndex={-1}>Late heading</h2> : <p>Loading</p>}</SettingsLayout>
            </div>
        );
        const { rerender } = render(<Late show={false} />);
        nav.pathname = '/acme/dashboard/forms/f1/settings/automations';
        rerender(<Late show={false} />);
        await flushFrame();
        expect(document.activeElement).toBe(document.body);
        rerender(<Late show />);
        await act(async () => void (await new Promise((resolve) => setTimeout(resolve, 20))));
        expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Late heading' }));
    });

    it('leaves focus alone when only the query changes (an automation sheet opening)', async () => {
        nav.pathname = '/acme/dashboard/forms/f1/settings/automations';
        const { rerender } = render(tree());
        rerender(tree());
        await flushFrame();
        expect(document.activeElement).toBe(document.body);
    });

    it("moves focus to the new page's heading, without scrolling", async () => {
        nav.pathname = '/acme/dashboard/forms/f1/settings/access';
        const { rerender } = render(tree());
        const focus = vi.spyOn(HTMLElement.prototype, 'focus');
        nav.pathname = '/acme/dashboard/forms/f1/settings/availability';
        rerender(tree());
        await flushFrame();
        expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Heading' }));
        expect(focus).toHaveBeenCalledWith({ preventScroll: true });
        focus.mockRestore();
    });
});

// The Automations cards: who sees which card, what each says, and the side
// sheets whose open state lives in the URL (?panel=).
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import commonNl from '../../../../public/locales/nl/common.json';
import AutomationsSection from './automations-section';

vi.stubGlobal(
    'ResizeObserver',
    class {
        observe() {}
        unobserve() {}
        disconnect() {}
    }
);

const url = vi.hoisted(() => ({ search: '' }));
const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }));
vi.mock('next/navigation', () => ({
    useRouter: () => nav,
    usePathname: () => '/acme/dashboard/forms/f1/settings',
    useSearchParams: () => new URLSearchParams(url.search)
}));

const served = vi.hoisted(() => ({
    permissions: [] as string[],
    webhooksOn: true,
    emailOn: true,
    mailServer: true,
    caseOn: true,
    hooks: undefined as any,
    emails: undefined as any,
    registration: undefined as any,
    webhookFailed: 0,
    emailFailed: 0,
    caseFailed: 0,
    caseDelivered: 0,
    integrations: [] as any[],
    needsReconnect: false
}));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (permission: string) => served.permissions.includes(permission), isLoading: false }) }));
const openModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal, closeModal: vi.fn() }) }));

const page = (total: number) => ({ data: { items: [], total }, isLoading: false, isError: false });
vi.mock('@app/store/workspaces/webhooks-api', async (original) => ({
    ...((await original()) as object),
    useGetWebhooksStatusQuery: () => ({ data: { enabled: served.webhooksOn }, isLoading: false }),
    useGetWebhooksQuery: (_arg: unknown, options?: { skip?: boolean }) => ({ data: options?.skip ? undefined : served.hooks, isLoading: false }),
    useGetWebhookDeliveriesQuery: () => page(served.webhookFailed)
}));
vi.mock('@app/store/workspaces/email-actions-api', async (original) => ({
    ...((await original()) as object),
    useGetEmailActionsStatusQuery: () => ({ data: { enabled: served.emailOn, configured: served.mailServer }, isLoading: false }),
    useGetEmailActionsQuery: (_arg: unknown, options?: { skip?: boolean }) => ({ data: options?.skip ? undefined : served.emails, isLoading: false }),
    useGetEmailDeliveriesQuery: () => page(served.emailFailed)
}));
vi.mock('@app/store/workspaces/registration-api', async (original) => ({
    ...((await original()) as object),
    useGetRegistrationStatusQuery: () => ({ data: { enabled: served.caseOn }, isLoading: false }),
    useGetFormRegistrationQuery: (_arg: unknown, options?: { skip?: boolean }) => ({ data: options?.skip ? undefined : served.registration, isLoading: false }),
    useGetRegistrationDeliveriesQuery: (arg: { status?: string[] }) => (arg.status?.includes('delivered') ? page(served.caseDelivered) : page(served.caseFailed))
}));
vi.mock('@app/store/api-actions-api', async (original) => ({
    ...((await original()) as object),
    useGetAllIntegrationsQuery: () => ({ data: served.integrations }),
    useGetActionReconsentStatusQuery: () => ({ data: { needs_reconsent: served.needsReconnect } })
}));

// The sheet bodies are the existing components, with their own tests: here only that they are used, headless.
vi.mock('@app/components/webhooks/webhooks-section', () => ({ default: () => null, WebhooksSettings: (props: any) => <div data-testid="body-webhooks" data-headless={String(!!props.headless)} /> }));
vi.mock('@app/components/webhooks/webhook-deliveries', () => ({ default: (props: any) => <div data-testid="body-webhooks-deliveries" data-headless={String(!!props.headless)} /> }));
vi.mock('@app/components/email-actions/email-actions-section', () => ({ default: () => null, EmailActionsSettings: (props: any) => <div data-testid="body-email" data-headless={String(!!props.headless)} /> }));
vi.mock('@app/components/email-actions/email-deliveries', () => ({ default: (props: any) => <div data-testid="body-email-deliveries" data-headless={String(!!props.headless)} /> }));
vi.mock('@app/components/registration/form-registration-settings', () => ({ default: () => null, FormRegistrationSettings: (props: any) => <div data-testid="body-case-system" data-headless={String(!!props.headless)} /> }));
vi.mock('@app/components/registration/deliveries-panel', () => ({ default: () => null, Deliveries: (props: any) => <div data-testid="body-case-system-deliveries" data-headless={String(!!props.headless)} /> }));
vi.mock('@app/components/form/integrations', () => ({ default: (props: any) => <div data-testid="body-action" data-only={props.onlyActionId} data-headless={String(!!props.headless)} /> }));

const MANAGE = ['workspace.manage', 'form.edit', 'response.read'];
const hook = (over: Record<string, unknown> = {}) => ({ id: 'w1', host: 'hooks.example', enabled: true, fields: [], hasSecret: true, ...over });
const sheetsAction = { id: 'a-sheets', name: 'integrate_google_sheets', title: 'Google Sheets', description: 'Adds each response to a spreadsheet.', url: '/integration/default.svg' };

const show = (opts: { permissions?: string[]; published?: boolean; provider?: string; added?: boolean; search?: string } = {}) => {
    served.permissions = opts.permissions ?? MANAGE;
    url.search = opts.search ?? '';
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(
        setForm({
            formId: 'f1',
            builderVersion: 'v2',
            title: 'Survey',
            isPublished: opts.published ?? true,
            settings: { provider: opts.provider ?? 'self' },
            actions: { on_submit: opts.added ? [{ id: 'a-sheets', enabled: true }] : [] }
        } as any)
    );
    return render(
        <ReduxProvider store={store}>
            <AutomationsSection />
        </ReduxProvider>
    );
};

const card = (name: string) => screen.getByTestId(`automation-card-${name}`);

beforeEach(() => {
    Object.assign(served, {
        webhooksOn: true,
        emailOn: true,
        mailServer: true,
        caseOn: true,
        hooks: [hook(), hook({ id: 'w2', host: 'crm.example' }), hook({ id: 'w3', host: 'old.example', enabled: false })],
        emails: [
            { id: 'e1', name: 'Team', enabled: true },
            { id: 'e2', name: 'Copy', enabled: true }
        ],
        registration: { enabled: true, serviceName: 'Case system Example' },
        webhookFailed: 0,
        emailFailed: 0,
        caseFailed: 0,
        caseDelivered: 0,
        integrations: [],
        needsReconnect: false
    });
    nav.push.mockClear();
    nav.replace.mockClear();
    nav.back.mockClear();
    openModal.mockClear();
});
afterEach(async () => {
    await act(async () => {
        await i18n.changeLanguage('en');
    });
});

describe('the cards', () => {
    it('shows one card each for email, webhooks and the case system, with a summary and a status in words', () => {
        show();
        expect(screen.getByRole('heading', { level: 2, name: 'Automations' })).toBeInTheDocument();
        expect(within(card('email')).getByRole('heading', { level: 3, name: 'Email' })).toBeInTheDocument();
        expect(within(card('email')).getByText('2 of 2 on')).toBeInTheDocument();
        expect(within(card('email')).getByTestId('automation-chip')).toHaveTextContent('On');
        expect(within(card('webhooks')).getByText('2 of 3 on · hooks.example, crm.example')).toBeInTheDocument();
        expect(within(card('webhooks')).getByTestId('automation-chip')).toHaveTextContent('On');
        expect(within(card('case-system')).getByText('Sends to Case system Example')).toBeInTheDocument();
        expect(within(card('case-system')).getByTestId('automation-chip')).toHaveTextContent('On');
    });

    it('names the buttons after the card', () => {
        show();
        expect(within(card('webhooks')).getByRole('button', { name: 'Manage Webhooks' })).toHaveTextContent('Manage');
        expect(within(card('webhooks')).getByRole('button', { name: 'Deliveries of Webhooks' })).toHaveTextContent('Deliveries');
        expect(within(card('email')).getByRole('button', { name: 'Manage Email' })).toBeInTheDocument();
        expect(within(card('case-system')).getByRole('button', { name: 'Deliveries of Case system' })).toBeInTheDocument();
    });

    it('says how many deliveries were not sent, instead of On', () => {
        served.webhookFailed = 1;
        served.emailFailed = 3;
        show();
        expect(within(card('webhooks')).getByTestId('automation-chip')).toHaveTextContent('1 not sent');
        expect(within(card('email')).getByTestId('automation-chip')).toHaveTextContent('3 not sent');
        expect(within(card('case-system')).getByTestId('automation-chip')).toHaveTextContent('On');
    });

    it('says Off when every entry is switched off', () => {
        served.hooks = [hook({ enabled: false })];
        show();
        expect(within(card('webhooks')).getByTestId('automation-chip')).toHaveTextContent('Off');
        expect(within(card('webhooks')).getByText('0 of 1 on')).toBeInTheDocument();
    });

    it('reads "Not set up" with a Set up button while nothing is configured, and no log to open', () => {
        served.hooks = [];
        served.emails = [];
        served.registration = { enabled: false, serviceName: null };
        show();
        for (const [name, label] of [
            ['webhooks', 'Webhooks'],
            ['email', 'Email'],
            ['case-system', 'Case system']
        ]) {
            expect(within(card(name)).getByTestId('automation-chip')).toHaveTextContent('Not set up');
            expect(within(card(name)).getByRole('button', { name: `Set up ${label}` })).toHaveTextContent('Set up');
            expect(within(card(name)).queryByRole('button', { name: /Manage/ })).toBeNull();
            expect(within(card(name)).queryByRole('button', { name: /Deliveries/ })).toBeNull();
        }
    });

    it('keeps the "no mail server" note as the email summary, with a status that says so', () => {
        served.mailServer = false;
        show();
        expect(within(card('email')).getByText(/no mail server set up/)).toBeInTheDocument();
        expect(within(card('email')).getByTestId('automation-chip')).toHaveTextContent('Cannot send');
    });

    it('gives an editor without workspace.manage the deliveries only, and no case-system card', () => {
        show({ permissions: ['form.edit'] });
        expect(within(card('webhooks')).queryByRole('button', { name: /Manage|Set up/ })).toBeNull();
        expect(within(card('webhooks')).getByRole('button', { name: 'Deliveries of Webhooks' })).toBeInTheDocument();
        expect(within(card('email')).queryByRole('button', { name: /Manage|Set up/ })).toBeNull();
        expect(within(card('email')).getByRole('button', { name: 'Deliveries of Email' })).toBeInTheDocument();
        expect(screen.queryByTestId('automation-card-case-system')).toBeNull();
    });

    it('does not render a card whose server switch is off', () => {
        served.webhooksOn = false;
        show();
        expect(screen.queryByTestId('automation-card-webhooks')).toBeNull();
        expect(screen.getByTestId('automation-card-email')).toBeInTheDocument();
    });

    it('does not render the section when no card is left', () => {
        served.webhooksOn = false;
        served.emailOn = false;
        served.caseOn = false;
        show();
        expect(screen.queryByRole('heading', { name: 'Automations' })).toBeNull();
    });

    it('shows nothing for a form imported from elsewhere', () => {
        show({ provider: 'google' });
        expect(screen.queryByRole('heading', { name: 'Automations' })).toBeNull();
    });

    it('has a card per integration action, for a published form built here', () => {
        served.integrations = [sheetsAction];
        show({ added: true });
        expect(within(card('action-a-sheets')).getByRole('heading', { level: 3, name: 'Google Sheets' })).toBeInTheDocument();
        expect(within(card('action-a-sheets')).getByText('Adds each response as a row in a Google spreadsheet.')).toBeInTheDocument();
        expect(within(card('action-a-sheets')).getByTestId('automation-chip')).toHaveTextContent('On');
        expect(within(card('action-a-sheets')).getByRole('button', { name: 'Manage Google Sheets' })).toBeInTheDocument();
        expect(within(card('action-a-sheets')).queryByRole('button', { name: /Deliveries/ })).toBeNull();
    });

    it('says "Reconnect needed" on an integration action that must be reconnected', () => {
        served.integrations = [sheetsAction];
        served.needsReconnect = true;
        show({ added: true });
        expect(within(card('action-a-sheets')).getByTestId('automation-chip')).toHaveTextContent('Reconnect needed');
    });

    it('sets an integration action up through the dialog it always used', () => {
        served.integrations = [sheetsAction];
        show({ added: false });
        expect(within(card('action-a-sheets')).getByTestId('automation-chip')).toHaveTextContent('Not set up');
        fireEvent.click(within(card('action-a-sheets')).getByRole('button', { name: 'Set up Google Sheets' }));
        expect(openModal).toHaveBeenCalledWith('ADD_ACTION_TO_FORM', expect.objectContaining({ action: sheetsAction }));
        expect(nav.push).not.toHaveBeenCalled();
    });

    it('has no integration cards for a draft', () => {
        served.integrations = [sheetsAction];
        show({ published: false });
        expect(screen.queryByTestId('automation-card-action-a-sheets')).toBeNull();
    });

    it('is Dutch in Dutch', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        served.webhookFailed = 2;
        show();
        const nl = (commonNl as any).STAFF.FORM_SETTINGS;
        expect(screen.getByRole('heading', { level: 2, name: nl.AUTOMATIONS })).toBeInTheDocument();
        expect(within(card('webhooks')).getByText('2 van 3 aan · hooks.example, crm.example')).toBeInTheDocument();
        expect(within(card('webhooks')).getByTestId('automation-chip')).toHaveTextContent('2 niet verstuurd');
        expect(within(card('webhooks')).getByRole('button', { name: 'Webhooks beheren' })).toHaveTextContent('Beheren');
        expect(within(card('webhooks')).getByRole('button', { name: 'Leveringen van Webhooks' })).toHaveTextContent('Leveringen');
        expect(within(card('case-system')).getByText('Verstuurt naar Case system Example')).toBeInTheDocument();
    });

    it('says what a known integration does in Dutch, and keeps the catalog text for one it does not know', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        served.integrations = [sheetsAction, { id: 'a-other', name: 'integrate_something_new', title: 'Something new', description: 'Catalog text.', url: '/integration/default.svg' }];
        show({ added: true });
        expect(within(card('action-a-sheets')).getByText('Voegt elke reactie toe als rij in een Google-spreadsheet.')).toBeInTheDocument();
        expect(within(card('action-a-other')).getByText('Catalog text.')).toBeInTheDocument();
    });

    it('has no accessibility violations', async () => {
        served.integrations = [sheetsAction];
        const { container } = show({ added: true });
        expect(await axeViolations(container)).toEqual([]);
    });
});

describe('the side sheets and the URL', () => {
    it('opens a sheet by adding ?panel= to the URL (Back closes it), keeping other parameters', () => {
        show({ search: 'lang=nl' });
        fireEvent.click(within(card('webhooks')).getByRole('button', { name: 'Manage Webhooks' }));
        expect(nav.push).toHaveBeenCalledWith('/acme/dashboard/forms/f1/settings?lang=nl&panel=webhooks', { scroll: false });
        fireEvent.click(within(card('email')).getByRole('button', { name: 'Deliveries of Email' }));
        expect(nav.push).toHaveBeenLastCalledWith('/acme/dashboard/forms/f1/settings?lang=nl&panel=email-deliveries', { scroll: false });
    });

    it('opens the settings sheet for ?panel=webhooks: a named dialog with the existing section as its body, headless', () => {
        show({ search: 'panel=webhooks' });
        const dialog = screen.getByRole('dialog', { name: 'Webhooks' });
        expect(within(dialog).getByTestId('body-webhooks')).toHaveAttribute('data-headless', 'true');
        expect(dialog).toHaveAccessibleDescription(/https address/);
        expect(within(dialog).getByRole('button', { name: 'Close' })).toBeInTheDocument();
    });

    it('opens the deliveries drawer for ?panel=email-deliveries with the existing log as its body', () => {
        show({ search: 'panel=email-deliveries' });
        const dialog = screen.getByRole('dialog', { name: 'Email: deliveries' });
        expect(within(dialog).getByTestId('body-email-deliveries')).toHaveAttribute('data-headless', 'true');
    });

    it('opens the case-system sheet and drawer', () => {
        const { unmount } = show({ search: 'panel=case-system' });
        expect(within(screen.getByRole('dialog', { name: 'Case system' })).getByTestId('body-case-system')).toHaveAttribute('data-headless', 'true');
        unmount();
        show({ search: 'panel=case-system-deliveries' });
        expect(within(screen.getByRole('dialog', { name: 'Case system: deliveries' })).getByTestId('body-case-system-deliveries')).toBeInTheDocument();
    });

    it("opens an integration action's sheet with just that action", () => {
        served.integrations = [sheetsAction];
        show({ added: true, search: 'panel=action-a-sheets' });
        const dialog = screen.getByRole('dialog', { name: 'Google Sheets' });
        expect(within(dialog).getByTestId('body-action')).toHaveAttribute('data-only', 'a-sheets');
    });

    it('opens nothing for a value that is not on the allow-list, or names something that is not there', () => {
        for (const search of ['panel=evil', 'panel=__proto__', 'panel=action-nope', 'panel=action-a/b', 'panel=Webhooks']) {
            served.integrations = [sheetsAction];
            const { unmount } = show({ added: true, search });
            expect(screen.queryByRole('dialog')).toBeNull();
            unmount();
        }
    });

    it('does not open the settings of a card the member may not configure', () => {
        const { unmount } = show({ permissions: ['form.edit'], search: 'panel=webhooks' });
        expect(screen.queryByRole('dialog')).toBeNull();
        unmount();
        show({ permissions: ['form.edit'], search: 'panel=webhooks-deliveries' });
        expect(screen.getByRole('dialog', { name: 'Webhooks: deliveries' })).toBeInTheDocument();
    });

    it('does not open a sheet for a card whose server switch is off', () => {
        served.webhooksOn = false;
        show({ search: 'panel=webhooks' });
        expect(screen.queryByRole('dialog')).toBeNull();
    });

    it('closes on Escape by replacing the URL when a link opened the sheet', () => {
        show({ search: 'panel=webhooks' });
        fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
        expect(nav.replace).toHaveBeenCalledWith('/acme/dashboard/forms/f1/settings', { scroll: false });
        expect(nav.back).not.toHaveBeenCalled();
    });

    it('goes back, not forward, when the sheet this page opened is closed', () => {
        const { rerender } = show();
        fireEvent.click(within(card('webhooks')).getByRole('button', { name: 'Manage Webhooks' }));
        url.search = 'panel=webhooks';
        rerender(
            <ReduxProvider store={store}>
                <AutomationsSection />
            </ReduxProvider>
        );
        fireEvent.click(within(screen.getByRole('dialog', { name: 'Webhooks' })).getByRole('button', { name: 'Close' }));
        expect(nav.back).toHaveBeenCalledTimes(1);
        expect(nav.replace).not.toHaveBeenCalled();
    });

    it('returns focus to the button that opened the sheet', async () => {
        const { rerender } = show();
        const manage = within(card('webhooks')).getByRole('button', { name: 'Manage Webhooks' });
        manage.focus();
        fireEvent.click(manage);
        url.search = 'panel=webhooks';
        const again = () => (
            <ReduxProvider store={store}>
                <AutomationsSection />
            </ReduxProvider>
        );
        rerender(again());
        expect(screen.getByRole('dialog', { name: 'Webhooks' })).toBeInTheDocument();
        url.search = '';
        rerender(again());
        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
        });
        expect(document.activeElement).toBe(within(card('webhooks')).getByRole('button', { name: 'Manage Webhooks' }));
    });

    it('has no accessibility violations with a sheet open', async () => {
        show({ search: 'panel=webhooks' });
        expect(await axeViolations(screen.getByRole('dialog'))).toEqual([]);
    });
});

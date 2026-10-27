import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import type { FormRegistration, RegistrationDelivery } from '@app/store/workspaces/registration-api';
import { axeViolations } from '@app/test/axe';
import { DELIVERY_ERROR_CODES } from '@app/utils/registration';

import enBuilder from '../../../public/locales/en/builder.json';
import nlBuilder from '../../../public/locales/nl/builder.json';
import DeliveriesPanel, { Deliveries } from './deliveries-panel';

const en = enBuilder.REGISTRATION as any;
const nl = nlBuilder.REGISTRATION as any;

const status = { data: { enabled: true } as { enabled: boolean } | undefined, isLoading: false };
const registrationState: { data: FormRegistration | undefined; isLoading: boolean; isError?: boolean } = { data: undefined, isLoading: false, isError: false };
const lists: Record<string, { data: { items: RegistrationDelivery[]; total: number } | undefined; isLoading: boolean; isError: boolean }> = {};
const queries: any[] = [];
const pollOptions: any[] = [];
const retryMock = vi.fn();
const refetchMock = vi.fn();
vi.mock('@app/store/workspaces/registration-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetRegistrationStatusQuery: () => status,
        useGetFormRegistrationQuery: () => registrationState,
        useGetRegistrationDeliveriesQuery: (arg: any, options?: any) => {
            queries.push(arg);
            if (options) pollOptions.push(options);
            return lists[(arg.status ?? []).join(',')] ?? { data: { items: [], total: 0 }, isLoading: false, isError: false, refetch: refetchMock };
        },
        useRetryRegistrationDeliveryMutation: () => [retryMock, { isLoading: false }]
    };
});

let permissions = new Set<string>();
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (p: string) => permissions.has(p), ready: true, isLoading: false }) }));
vi.mock('@app/store/forms/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectForm: () => ({ formId: 'f1' }) };
});
vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme' }) };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

const delivery = (over: Partial<RegistrationDelivery> = {}): RegistrationDelivery => ({
    id: 'd1',
    responseId: 'resp-0001',
    status: 'failed',
    serviceName: 'Cases',
    attempts: 6,
    manualAttempts: 0,
    lastErrorCode: 'http_5xx',
    lastHttpStatus: 503,
    lastAttemptAt: '2026-10-26T10:15:00Z',
    nextAttemptAt: null,
    deliveredAt: null,
    createdAt: '2026-10-26T09:00:00Z',
    ...over
});

const setLists = (failed: RegistrationDelivery[], failedTotal = failed.length, delivered = 12, waiting = 2) => {
    lists['failed,cancelled'] = { data: { items: failed, total: failedTotal }, isLoading: false, isError: false, refetch: refetchMock };
    lists['delivered'] = { data: { items: [], total: delivered }, isLoading: false, isError: false, refetch: refetchMock };
    lists['pending,in_progress,retrying'] = { data: { items: [], total: waiting }, isLoading: false, isError: false, refetch: refetchMock };
};

beforeEach(() => {
    status.data = { enabled: true };
    registrationState.data = { enabled: true, serviceId: 's1', serviceName: 'Cases', organisationName: 'Example Organisation', path: '', variables: [], transformToList: [] };
    registrationState.isError = false;
    permissions = new Set([WorkspacePermission.RESPONSE_READ, WorkspacePermission.FORM_EDIT]);
    Object.keys(lists).forEach((k) => delete lists[k]);
    queries.length = 0;
    pollOptions.length = 0;
    retryMock.mockReset();
    setLists([delivery()]);
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('Deliveries on the responses tab', () => {
    it('is hidden when the server has the feature off, and for members who cannot read responses', () => {
        status.data = { enabled: false };
        expect(render(<DeliveriesPanel />, { wrapper }).container).toBeEmptyDOMElement();
        status.data = { enabled: true };
        permissions = new Set([WorkspacePermission.FORM_READ]);
        expect(render(<DeliveriesPanel />, { wrapper }).container).toBeEmptyDOMElement();
    });

    it('is hidden for a form that never sent anything', () => {
        registrationState.data = { enabled: false, path: '', variables: [], transformToList: [] };
        setLists([], 0, 0, 0);
        expect(render(<DeliveriesPanel />, { wrapper }).container).toBeEmptyDOMElement();
    });

    it('stays visible for a form that stopped sending but still has deliveries', () => {
        registrationState.data = { enabled: false, path: '', variables: [], transformToList: [] };
        render(<DeliveriesPanel />, { wrapper });
        expect(screen.getByTestId('registration-deliveries')).toBeInTheDocument();
    });

    it('shows the counts and each not-sent submission with time, reason as a sentence, and ids only', () => {
        render(<DeliveriesPanel />, { wrapper });
        expect(screen.getByTestId('registration-count-delivered')).toHaveTextContent('12');
        expect(screen.getByTestId('registration-count-waiting')).toHaveTextContent('2');
        expect(screen.getByTestId('registration-count-failed')).toHaveTextContent('1');
        expect(screen.getByRole('alert')).toHaveTextContent('1 submission was not sent.');
        const row = screen.getByTestId('registration-delivery-d1');
        expect(row).toHaveTextContent('resp-0001');
        expect(row).toHaveTextContent(en.DELIVERY.STATUS.failed);
        expect(row).toHaveTextContent('The case system had an error (HTTP 503) on every attempt.');
        expect(row).toHaveTextContent(/Last attempt: .*2026/);
        expect(row).toHaveTextContent('6 attempts');
    });

    it('asks for the failed and cancelled ones, and the counts with a page of one', () => {
        render(<DeliveriesPanel />, { wrapper });
        expect(queries).toContainEqual({ workspaceId: 'ws1', formId: 'f1', status: ['failed', 'cancelled'], limit: 50 });
        expect(queries).toContainEqual({ workspaceId: 'ws1', formId: 'f1', status: ['delivered'], limit: 1 });
        expect(queries).toContainEqual({ workspaceId: 'ws1', formId: 'f1', status: ['pending', 'in_progress', 'retrying'], limit: 1 });
    });

    it.each(DELIVERY_ERROR_CODES)('words the reason "%s"', (code) => {
        setLists([delivery({ lastErrorCode: code, lastHttpStatus: 502 })]);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.getByTestId('registration-delivery-d1')).toHaveTextContent((en.DELIVERY.ERROR[code] as string).replace('{{status}}', '502'));
    });

    it('says what the creator can do for every code, in both languages', async () => {
        const nlText = nl.DELIVERY.ERROR as Record<string, string>;
        for (const code of DELIVERY_ERROR_CODES) {
            expect(en.DELIVERY.ERROR[code].length, code).toBeGreaterThan(30);
            expect(nlText[code].length, code).toBeGreaterThan(30);
        }
        // the dashboard speaks "u", never "je"
        expect(Object.values(nlText).join(' ')).not.toMatch(/\b(je|jouw|jij)\b/i);
    });

    it('words a lookup failure and says nothing was sent again', () => {
        registrationState.data = { ...registrationState.data!, kind: 'objects_api' };
        setLists([delivery({ lastErrorCode: 'lookup_failed', lastHttpStatus: 403 })]);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        const row = screen.getByTestId('registration-delivery-d1');
        expect(row).toHaveTextContent("We couldn't confirm whether the record already exists in the Objects API, so nothing was sent again.");
        expect(within(row).getByRole('button', { name: /Retry/ })).toBeInTheDocument();
    });

    it('words a config_invalid and an internal_error failure', () => {
        setLists([delivery({ id: 'd1', lastErrorCode: 'config_invalid' }), delivery({ id: 'd2', lastErrorCode: 'internal_error' })]);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.getByTestId('registration-delivery-d1')).toHaveTextContent('cannot be sent safely');
        expect(screen.getByTestId('registration-delivery-d2')).toHaveTextContent('Something went wrong on our side.');
    });

    it('reads an Objects API refusal with status 400 as a schema mismatch, and only for that kind', () => {
        setLists([delivery({ lastErrorCode: 'http_4xx', lastHttpStatus: 400 })]);
        const first = render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.getByTestId('registration-delivery-d1')).toHaveTextContent('The case system refused the submission (HTTP 400).');
        first.unmount();
        registrationState.data = { ...registrationState.data!, kind: 'objects_api' };
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.getByTestId('registration-delivery-d1')).toHaveTextContent('The object type did not accept the data (HTTP 400).');
    });

    it('reads an Objects API 401 or 403 as a refused token', () => {
        registrationState.data = { ...registrationState.data!, kind: 'objects_api' };
        setLists([delivery({ lastErrorCode: 'http_4xx', lastHttpStatus: 403 })]);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.getByTestId('registration-delivery-d1')).toHaveTextContent('The Objects API refused the token (HTTP 403).');
    });

    it('shows the created object id as text on a sent submission, once asked for', () => {
        registrationState.data = { ...registrationState.data!, kind: 'objects_api' };
        setLists([delivery()]);
        lists['delivered'] = {
            data: { items: [delivery({ id: 'd9', status: 'delivered', lastErrorCode: null, deliveredAt: '2026-10-26T10:20:00Z', remoteId: '5b3f6c1e-0000-4000-8000-000000000001' })], total: 1 },
            isLoading: false,
            isError: false,
            refetch: refetchMock
        };
        const { container } = render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.queryByTestId('registration-sent-d9')).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: en.DELIVERY.SHOW_DELIVERED }));
        const row = screen.getByTestId('registration-sent-d9');
        expect(row).toHaveTextContent('Object id: 5b3f6c1e-0000-4000-8000-000000000001');
        // plain text: never a link or an image the browser could fetch
        expect(container.querySelector('a, img')).toBeNull();
        expect(queries).toContainEqual({ workspaceId: 'ws1', formId: 'f1', status: ['delivered'], limit: 20 });
    });

    const sentItems = (count: number, total: number) => {
        lists['delivered'] = {
            data: { items: Array.from({ length: count }, (_, i) => delivery({ id: `s${i}`, status: 'delivered', lastErrorCode: null, deliveredAt: '2026-10-26T10:20:00Z' })), total },
            isLoading: false,
            isError: false,
            refetch: refetchMock
        };
    };

    it('pages the sent submissions: 20 at a time, with the total and a way to see more', () => {
        setLists([delivery()]);
        sentItems(20, 45);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: en.DELIVERY.SHOW_DELIVERED }));
        expect(screen.getByText('Showing 20 of 45')).toBeInTheDocument();
        expect(queries).toContainEqual({ workspaceId: 'ws1', formId: 'f1', status: ['delivered'], limit: 20 });
        const more = within(screen.getByTestId('registration-deliveries')).getAllByRole('button', { name: en.DELIVERY.SHOW_MORE }).at(-1)!;
        fireEvent.click(more);
        expect(queries).toContainEqual({ workspaceId: 'ws1', formId: 'f1', status: ['delivered'], limit: 40 });
    });

    it('shows no "show more" once every sent submission is listed', () => {
        setLists([delivery()]);
        sentItems(3, 3);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: en.DELIVERY.SHOW_DELIVERED }));
        expect(screen.getByText('Showing 3 of 3')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: en.DELIVERY.SHOW_MORE })).toBeNull();
    });

    it('reads the sent list again, with the others, when the waiting count moves', () => {
        setLists([delivery()], 1, 12, 2);
        sentItems(2, 12);
        const { rerender } = render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: en.DELIVERY.SHOW_DELIVERED }));
        refetchMock.mockClear();
        setLists([delivery()], 1, 12, 1);
        sentItems(2, 12);
        rerender(<Deliveries workspaceId="ws1" formId="f1" canRetry />);
        // failed, delivered counts and the sent list
        expect(refetchMock).toHaveBeenCalledTimes(3);
    });

    it("says so when the form's settings could not be read, instead of showing nothing", () => {
        registrationState.data = undefined;
        registrationState.isError = true;
        setLists([], 0, 0, 0);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.getByRole('alert')).toHaveTextContent(en.DELIVERY.REGISTRATION_ERROR);
    });

    it('shows no object id for a Generic JSON delivery', () => {
        setLists([delivery()]);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.queryByTestId('registration-object-id')).toBeNull();
    });

    it("never shows an unknown code or the destination's text, only a plain sentence", () => {
        setLists([delivery({ lastErrorCode: '<img src=x onerror=alert(1)>' })]);
        const { container } = render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(container.querySelector('img')).toBeNull();
        expect(screen.getByTestId('registration-delivery-d1')).toHaveTextContent(en.DELIVERY.ERROR.unknown);
    });

    it('shows a cancelled delivery as cancelled', () => {
        setLists([delivery({ status: 'cancelled', lastErrorCode: null })]);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        const row = screen.getByTestId('registration-delivery-d1');
        expect(row).toHaveTextContent(en.DELIVERY.STATUS.cancelled);
        expect(row).toHaveTextContent(en.DELIVERY.CANCELLED_REASON);
    });

    it("retries through the endpoint with the delivery's own id", async () => {
        retryMock.mockResolvedValue({ data: delivery({ status: 'pending' }) });
        render(<DeliveriesPanel />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Retry sending submission resp-0001' }));
        await waitFor(() => expect(retryMock).toHaveBeenCalledTimes(1));
        expect(retryMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', deliveryId: 'd1' });
        expect(await screen.findByText(en.DELIVERY.RETRY_STARTED)).toBeInTheDocument();
    });

    it('keeps the answer after the retried row has left the list', async () => {
        retryMock.mockImplementation(async () => {
            // the delivery is pending now: it is no longer in the failed list
            setLists([], 0, 12, 3);
            return { data: delivery({ status: 'pending' }) };
        });
        const { rerender } = render(<DeliveriesPanel />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: /Retry sending submission/ }));
        await waitFor(() => expect(retryMock).toHaveBeenCalled());
        rerender(<DeliveriesPanel />);
        expect(screen.queryByTestId('registration-delivery-d1')).toBeNull();
        expect(await screen.findByText(en.DELIVERY.RETRY_STARTED)).toBeInTheDocument();
        expect(screen.getByText(en.DELIVERY.RETRY_STARTED)).toHaveAttribute('role', 'status');
        // the waiting count moved (2 -> 3): the other lists are read again
        expect(refetchMock).toHaveBeenCalled();
    });

    it('asks for the waiting count again every few seconds', () => {
        render(<DeliveriesPanel />, { wrapper });
        expect(pollOptions).toContainEqual({ pollingInterval: 10000 });
    });

    it('explains a delivery that can no longer be retried', async () => {
        retryMock.mockResolvedValue({ error: { status: 409, data: { code: 'not_retryable', message: 'RAW SERVER TEXT' } } });
        render(<DeliveriesPanel />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: /Retry sending submission/ }));
        const message = await screen.findByText(en.ERROR.not_retryable);
        expect(message).toBeInTheDocument();
        expect(document.body).not.toHaveTextContent('RAW SERVER TEXT');
    });

    it('offers no Retry to members who cannot edit the form', () => {
        permissions = new Set([WorkspacePermission.RESPONSE_READ]);
        render(<DeliveriesPanel />, { wrapper });
        expect(screen.getByTestId('registration-delivery-d1')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Retry/ })).toBeNull();
    });

    it('says so when nothing failed, and offers more when there are more than shown', () => {
        setLists([], 0);
        const { unmount } = render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.getByText(en.DELIVERY.NONE_FAILED)).toBeInTheDocument();
        unmount();
        setLists([delivery()], 120);
        render(<Deliveries workspaceId="ws1" formId="f1" canRetry />, { wrapper });
        expect(screen.getByRole('alert')).toHaveTextContent('120 submissions were not sent.');
        fireEvent.click(screen.getByRole('button', { name: en.DELIVERY.SHOW_MORE }));
        expect(queries).toContainEqual({ workspaceId: 'ws1', formId: 'f1', status: ['failed', 'cancelled'], limit: 100 });
    });

    it('speaks Dutch', async () => {
        await i18n.changeLanguage('nl');
        render(<DeliveriesPanel />, { wrapper });
        const row = screen.getByTestId('registration-delivery-d1');
        expect(row).toHaveTextContent(nl.DELIVERY.STATUS.failed);
        expect(row).toHaveTextContent('Het zaaksysteem had bij elke poging een fout (HTTP 503).');
        expect(screen.getByRole('alert')).toHaveTextContent('1 inzending is niet verstuurd.');
        within(row).getByRole('button', { name: /opnieuw proberen/i });
    });
});

describe('Accessibility', () => {
    it('passes axe (WCAG 2.1 A/AA) with a failed delivery', async () => {
        render(<DeliveriesPanel />, { wrapper });
        expect(await axeViolations(document.body)).toEqual([]);
    });
});

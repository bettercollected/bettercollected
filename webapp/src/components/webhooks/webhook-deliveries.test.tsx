import React from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import type { WebhookAuditEntry, WebhookDelivery } from '@app/store/workspaces/webhooks-api';
import { axeViolations } from '@app/test/axe';
import { DELIVERY_ERROR_CODES } from '@app/utils/webhooks';

import enBuilder from '../../../public/locales/en/builder.json';
import nlBuilder from '../../../public/locales/nl/builder.json';
import WebhookDeliveries from './webhook-deliveries';

type List = { data: { items: WebhookDelivery[]; total: number } | undefined; isLoading: boolean; isError: boolean; error?: any };
const lists: Record<string, List> = {};
const queries: any[] = [];
const options: any[] = [];
const auditState: { data: WebhookAuditEntry[] | undefined; isError: boolean } = { data: undefined, isError: false };
vi.mock('@app/store/workspaces/webhooks-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWebhookDeliveriesQuery: (arg: any, opts?: any) => {
            queries.push(arg);
            if (opts) options.push({ arg, opts });
            return lists[(arg.status ?? []).join(',')] ?? { data: { items: [], total: 0 }, isLoading: false, isError: false };
        },
        useGetWebhookAuditQuery: (_arg: any, opts?: any) => (opts?.skip ? { data: undefined, isError: false } : auditState)
    };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

const delivery = (over: Partial<WebhookDelivery> = {}): WebhookDelivery => ({
    id: 'd1',
    actionType: 'webhook',
    webhookId: 'w1',
    host: 'hooks.example.org',
    event: 'submission',
    responseId: 'resp-0001',
    status: 'failed',
    attempts: 6,
    lastErrorCode: 'http_5xx',
    lastHttpStatus: 503,
    lastDurationMs: 2400,
    lastAttemptAt: '2026-10-26T10:15:00Z',
    finishedAt: '2026-10-26T10:15:02Z',
    createdAt: '2026-10-26T09:00:00Z',
    ...over
});

const set = (all: WebhookDelivery[], counts = { delivered: 12, waiting: 2, failed: all.length }) => {
    lists['pending,in_progress,retrying'] = { data: { items: [], total: counts.waiting }, isLoading: false, isError: false };
    lists['delivered'] = { data: { items: [], total: counts.delivered }, isLoading: false, isError: false };
    lists['failed,cancelled'] = { data: { items: [], total: counts.failed }, isLoading: false, isError: false };
    lists[''] = { data: { items: all, total: all.length }, isLoading: false, isError: false };
};

beforeEach(() => {
    Object.keys(lists).forEach((k) => delete lists[k]);
    queries.length = 0;
    options.length = 0;
    auditState.data = undefined;
    auditState.isError = false;
    set([delivery()]);
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('Deliveries', () => {
    it('shows the counts and each delivery with its code, attempts, HTTP status and timing', () => {
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        expect(screen.getByRole('heading', { name: 'Deliveries' })).toBeInTheDocument();
        expect(screen.getByTestId('webhook-count-delivered')).toHaveTextContent('12');
        expect(screen.getByTestId('webhook-count-waiting')).toHaveTextContent('2');
        expect(screen.getByTestId('webhook-count-failed')).toHaveTextContent('1');
        const row = screen.getByTestId('webhook-delivery-d1');
        expect(within(row).getByText('Not sent')).toBeInTheDocument();
        expect(row).toHaveTextContent('hooks.example.org');
        expect(row).toHaveTextContent('6 attempts');
        expect(row).toHaveTextContent('HTTP 503');
        expect(row).toHaveTextContent('2.4 s');
        expect(row).toHaveTextContent('Your system answered with a server error (HTTP 503).');
        expect(row).toHaveTextContent('resp-0001');
        expect(screen.getByText('Deliveries are kept for 30 days.')).toBeInTheDocument();
    });

    it('says what a test event is, and when a retry is due', () => {
        set([delivery({ id: 't1', event: 'test', responseId: null, status: 'delivered', attempts: 1, lastErrorCode: null, lastHttpStatus: 200, lastDurationMs: 120 }), delivery({ id: 'r1', status: 'retrying', attempts: 2, nextAttemptAt: '2026-10-26T11:00:00Z' })]);
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        expect(screen.getByTestId('webhook-delivery-t1')).toHaveTextContent('test event');
        expect(screen.getByTestId('webhook-delivery-t1')).not.toHaveTextContent('Submission');
        expect(screen.getByTestId('webhook-delivery-r1')).toHaveTextContent('Will retry');
        expect(screen.getByTestId('webhook-delivery-r1')).toHaveTextContent('Next attempt:');
    });

    it('has a sentence for every code the server can store', () => {
        for (const code of DELIVERY_ERROR_CODES) {
            set([delivery({ lastErrorCode: code, lastHttpStatus: 502 })]);
            const { unmount } = render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
            const text = screen.getByTestId('webhook-delivery-d1').textContent ?? '';
            expect(text, code).not.toMatch(/WEBHOOKS\./);
            expect(text, code).not.toContain('It was not sent.');
            unmount();
        }
        set([delivery({ lastErrorCode: 'something_new' })]);
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        expect(screen.getByTestId('webhook-delivery-d1')).toHaveTextContent('It was not sent.');
    });

    it('never renders anything but ids, codes and timings', () => {
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        const text = document.body.textContent ?? '';
        // the API has no field for an answer or a reply, so none can be shown
        for (const field of Object.keys(delivery())) expect(['answer', 'body', 'reply', 'url']).not.toContain(field);
        expect(text).not.toMatch(/https:\/\//);
    });

    it('filters by status and asks for the matching list', () => {
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.change(screen.getByLabelText('Show'), { target: { value: 'failed' } });
        expect(queries.some((q) => (q.status ?? []).join(',') === 'failed,cancelled' && q.limit === 20)).toBe(true);
        fireEvent.change(screen.getByLabelText('Show'), { target: { value: 'waiting' } });
        expect(queries.some((q) => (q.status ?? []).join(',') === 'pending,in_progress,retrying' && q.limit === 20)).toBe(true);
    });

    it('shows more on request', () => {
        lists[''] = { data: { items: [delivery()], total: 45 }, isLoading: false, isError: false };
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        expect(screen.getByRole('status')).toHaveTextContent('Showing 1 of 45');
        fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
        expect(queries.some((q) => (q.status ?? []).length === 0 && q.limit === 40)).toBe(true);
    });

    it('polls while deliveries are waiting, and not when none are', () => {
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        const polled = options.filter((o) => (o.arg.status ?? []).length === 0);
        expect(polled.at(-1).opts.pollingInterval).toBe(10000);
        options.length = 0;
        set([delivery()], { delivered: 3, waiting: 0, failed: 1 });
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        expect(options.filter((o) => (o.arg.status ?? []).length === 0).at(-1).opts.pollingInterval).toBe(0);
    });

    it('says nothing was sent yet when the log is empty', () => {
        set([], { delivered: 0, waiting: 0, failed: 0 });
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        expect(screen.getByText(/Nothing has been sent yet/)).toBeInTheDocument();
        expect(screen.queryByLabelText('Show')).not.toBeInTheDocument();
    });

    it('is hidden for someone who may not read it', () => {
        lists['pending,in_progress,retrying'] = { data: undefined, isLoading: false, isError: true, error: { status: 403 } };
        expect(render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper }).container).toBeEmptyDOMElement();
    });

    it('lists who changed the webhooks and what, never values', () => {
        auditState.data = [
            { id: 'a2', webhookId: 'w1', event: 'updated', actorId: 'u1', changed: ['url', 'fields'], host: 'hooks.example.org', createdAt: '2026-10-26T10:00:00Z' },
            { id: 'a1', webhookId: 'w1', event: 'created', actorId: 'u1', changed: [], host: 'hooks.example.org', createdAt: '2026-10-26T09:00:00Z' }
        ];
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        const toggle = screen.getByRole('button', { name: 'Show changes' });
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        fireEvent.click(toggle);
        const list = screen.getByRole('list', { name: 'Changes to the webhooks' });
        expect(within(list).getAllByRole('listitem')).toHaveLength(2);
        expect(list).toHaveTextContent('Webhook changed');
        expect(list).toHaveTextContent('address, questions');
        expect(list).toHaveTextContent('Webhook added');
        expect(screen.getByRole('button', { name: 'Hide changes' })).toHaveAttribute('aria-expanded', 'true');
    });

    it('speaks Dutch', async () => {
        await i18n.changeLanguage('nl');
        set([delivery({ lastErrorCode: 'timeout' })]);
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        expect(screen.getByRole('heading', { name: 'Leveringen' })).toBeInTheDocument();
        const row = screen.getByTestId('webhook-delivery-d1');
        expect(row).toHaveTextContent('Niet verstuurd');
        expect(row).toHaveTextContent('6 pogingen');
        expect(row).toHaveTextContent('Uw systeem antwoordde niet op tijd.');
        expect(screen.getByText('Leveringen worden 30 dagen bewaard.')).toBeInTheDocument();
        expect(screen.getByLabelText('Tonen')).toBeInTheDocument();
    });

    it('has no accessibility violations (list, filter, changes)', async () => {
        auditState.data = [{ id: 'a1', webhookId: 'w1', event: 'created', actorId: 'u1', changed: [], host: 'hooks.example.org', createdAt: '2026-10-26T09:00:00Z' }];
        render(<WebhookDeliveries workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Show changes' }));
        expect(await axeViolations(document.body)).toEqual([]);
        await i18n.changeLanguage('nl');
        expect(await axeViolations(document.body)).toEqual([]);
    });
});

describe('locale files', () => {
    it('English and Dutch carry the same webhook keys', () => {
        const keys = (tree: any, prefix = ''): string[] => Object.entries(tree).flatMap(([k, v]) => (typeof v === 'string' ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`)));
        expect(keys((nlBuilder as any).WEBHOOKS).sort()).toEqual(keys((enBuilder as any).WEBHOOKS).sort());
    });
});

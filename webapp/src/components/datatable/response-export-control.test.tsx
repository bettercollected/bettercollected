import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import I18nProvider from '@app/shared/hocs/i18n-provider';

import commonEn from '../../../public/locales/en/common.json';
import commonNl from '../../../public/locales/nl/common.json';
import ResponseExportControl, { EXPORT_POLL_MS } from './response-export-control';

// The "server": what starting an export answers, the exports already there, the
// export being followed and the file. Every call the control makes is recorded.
const server: {
    started: any;
    startError: any;
    mine: any[];
    status: any;
    statusOptions: any[];
    downloadError: any;
    starts: any[];
    downloads: any[];
    saved: Array<{ blob: Blob; name: string }>;
} = { started: undefined, startError: undefined, mine: [], status: undefined, statusOptions: [], downloadError: undefined, starts: [], downloads: [], saved: [] };

vi.mock('@app/utils/response-export', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, downloadBlob: (blob: Blob, name: string) => server.saved.push({ blob, name }) };
});

vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useStartResponseExportMutation: () => [
            (arg: any) => ({
                unwrap: async () => {
                    server.starts.push(arg);
                    if (server.startError) throw server.startError;
                    return server.started;
                }
            })
        ],
        useGetResponseExportsQuery: () => ({ data: server.mine, refetch: () => ({ unwrap: async () => server.mine }) }),
        useGetResponseExportQuery: (arg: any, options: any) => {
            server.statusOptions.push({ arg, options });
            return { data: options?.skip ? undefined : server.status, refetch: () => ({ unwrap: async () => server.status }) };
        },
        useDownloadResponseExportMutation: () => [
            (arg: any) => ({
                unwrap: async () => {
                    server.downloads.push(arg);
                    if (server.downloadError) throw server.downloadError;
                    return new Blob(['csv']);
                }
            })
        ]
    };
});

const tree = (props: any = {}) => (
    <I18nProvider>
        <ResponseExportControl workspaceId="ws-1" formId="form-1" formTitle="Colours" {...props} />
    </I18nProvider>
);

const job = (over: Record<string, any> = {}) => ({ id: 'exp-1', formId: 'form-1', kind: 'job', status: 'queued', format: 'csv', fileName: 'Colours.csv', ...over });
const ready = (over: Record<string, any> = {}) => job({ status: 'ready', downloadUrl: '/workspaces/ws-1/forms/form-1/exports/exp-1/download?token=1.abc', expiresAt: '2026-11-01T10:00:00Z', ...over });
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }));
const lastStatusQuery = () => server.statusOptions.at(-1);

beforeEach(() => {
    Object.assign(server, { started: undefined, startError: undefined, mine: [], status: undefined, statusOptions: [], downloadError: undefined, starts: [], downloads: [], saved: [] });
});

describe('a small export', () => {
    it('downloads at once, from the response itself', async () => {
        server.started = { kind: 'file', blob: new Blob(['a,b']), mediaType: 'text/csv; charset=utf-8' };
        render(tree());
        click('Export CSV');
        await waitFor(() => expect(server.saved).toHaveLength(1));
        expect(server.saved[0].name).toBe('Colours.csv');
        expect(server.starts).toEqual([{ workspaceId: 'ws-1', formId: 'form-1' }]);
        expect(await screen.findByText('Your export was downloaded.')).toBeInTheDocument();
        expect(screen.queryByText(/preparing your export/i)).toBeNull();
        // nothing was kept on the server, so nothing says it was deleted
        expect(screen.queryByText(/deleted the file/i)).toBeNull();
    });

    it('is a ZIP when the form has a table of its own', async () => {
        server.started = { kind: 'file', blob: new Blob(['PK']), mediaType: 'application/zip' };
        render(tree());
        click('Export CSV');
        await waitFor(() => expect(server.saved).toHaveLength(1));
        expect(server.saved[0].name).toBe('Colours.zip');
    });

    it('holds what the list shows: the search goes with the request', async () => {
        server.started = { kind: 'file', blob: new Blob(['a']), mediaType: 'text/csv' };
        render(tree({ search: 'sita@example.org' }));
        click('Export matching responses');
        await waitFor(() => expect(server.starts).toHaveLength(1));
        expect(server.starts[0]).toEqual({ workspaceId: 'ws-1', formId: 'form-1', search: 'sita@example.org' });
    });

    it('can be dismissed, and started again', async () => {
        server.started = { kind: 'file', blob: new Blob(['a']), mediaType: 'text/csv' };
        render(tree());
        click('Export CSV');
        await screen.findByText('Your export was downloaded.');
        click('Dismiss');
        expect(screen.queryByText('Your export was downloaded.')).toBeNull();
        click('Export CSV');
        await waitFor(() => expect(server.saved).toHaveLength(2));
    });
});

describe('a large export', () => {
    it('is prepared by the server, then handed over through a fresh link', async () => {
        server.started = { kind: 'job', export: job() };
        const { rerender } = render(tree());
        click('Export CSV');
        const status = await screen.findByRole('status');
        expect(status).toHaveTextContent("We're preparing your export");
        // the button waits, announced politely; the export is followed every few seconds
        expect(screen.getByRole('button', { name: 'Export CSV' })).toBeDisabled();
        expect(status).toHaveAttribute('aria-live', 'polite');
        expect(status).toHaveAttribute('aria-busy', 'true');
        expect(lastStatusQuery()).toMatchObject({ arg: { workspaceId: 'ws-1', formId: 'form-1', exportId: 'exp-1' }, options: { skip: false, pollingInterval: EXPORT_POLL_MS } });

        // the job ends: the link appears
        server.status = ready();
        rerender(tree());
        expect(await screen.findByText('Your export is ready.')).toBeInTheDocument();
        expect(screen.getByText(/deleted when you download it/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Export CSV' })).not.toBeDisabled();
        // a ready export is not polled
        expect(lastStatusQuery().options.pollingInterval).toBe(0);

        click('Download');
        await waitFor(() => expect(server.saved).toHaveLength(1));
        // the link used is the one of a fresh status read
        expect(server.downloads).toEqual([{ downloadUrl: '/workspaces/ws-1/forms/form-1/exports/exp-1/download?token=1.abc' }]);
        expect(server.saved[0].name).toBe('Colours.csv');
        expect(await screen.findByText('Your export was downloaded.')).toBeInTheDocument();
        expect(screen.getByText(/We deleted the file from our servers/)).toBeInTheDocument();
    });

    it('follows the same export through queued and running', async () => {
        server.started = { kind: 'job', export: job() };
        server.status = job({ status: 'running' });
        render(tree());
        click('Export CSV');
        expect(await screen.findByRole('status')).toHaveTextContent("We're preparing your export");
    });

    it('is found again after a reload: ready', async () => {
        server.mine = [ready()];
        server.status = ready();
        render(tree());
        expect(await screen.findByText('Your export is ready.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument();
    });

    it('is found again after a reload: still running', async () => {
        server.mine = [job({ status: 'running' })];
        server.status = job({ status: 'running' });
        render(tree());
        expect(await screen.findByRole('status')).toHaveTextContent("We're preparing your export");
        expect(screen.getByRole('button', { name: 'Export CSV' })).toBeDisabled();
    });

    it('says so when the last export ended without a file', async () => {
        server.mine = [job({ status: 'cancelled', errorCode: 'responses_deleted' })];
        render(tree());
        expect(await screen.findByRole('alert')).toHaveTextContent('Responses were deleted while your export was being prepared');
    });

    it('follows an export that is already running when a second is refused', async () => {
        server.startError = { status: 409, data: { code: 'export_in_progress' } };
        render(tree());
        server.mine = [job({ status: 'running' })];
        server.status = job({ status: 'running' });
        click('Export CSV');
        expect(await screen.findByText(/preparing your export/i)).toBeInTheDocument();
    });

    it.each([
        ['failed', undefined, 'could not be prepared'],
        ['failed', 'too_large', 'too large for one file'],
        ['cancelled', 'responses_deleted', 'Responses were deleted while your export'],
        ['cancelled', 'permission_removed', 'no longer export'],
        ['expired', undefined, 'no longer available'],
        ['erased', undefined, 'no longer available']
    ])('a %s export (%s) is explained', async (status, errorCode, words) => {
        server.started = { kind: 'job', export: job() };
        const { rerender } = render(tree());
        click('Export CSV');
        await screen.findByRole('status');
        server.status = job({ status, errorCode });
        rerender(tree());
        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent(words);
        expect(alert).toHaveAttribute('aria-live', 'assertive');
        expect(screen.getByRole('button', { name: 'Export CSV' })).not.toBeDisabled();
    });
});

describe('when it is refused', () => {
    it.each([
        [{ status: 429, data: { code: 'rate_limited', retryAfter: 125 } }, 'Try again in 3 minutes'],
        [{ status: 429, data: { code: 'rate_limited', retryAfter: 5 } }, 'Try again in 1 minutes'],
        [{ status: 413, data: { code: 'too_many_rows' } }, 'too many responses for one file'],
        [{ status: 403, data: {} }, 'not allowed to export'],
        [{ status: 500, data: {} }, 'did not work'],
        [{ status: 'FETCH_ERROR' }, 'did not work']
    ])('%j', async (error, words) => {
        server.startError = error;
        render(tree());
        click('Export CSV');
        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent(words);
        expect(server.saved).toEqual([]);
        expect(screen.getByRole('button', { name: 'Export CSV' })).not.toBeDisabled();
    });

    it('says a link that no longer works is gone', async () => {
        server.mine = [ready()];
        server.status = ready();
        server.downloadError = { status: 410, data: { code: 'export_gone' } };
        render(tree());
        await screen.findByText('Your export is ready.');
        click('Download');
        expect(await screen.findByRole('alert')).toHaveTextContent('no longer available');
    });

    it('names the refusal in the status region the button points to', async () => {
        server.startError = { status: 403, data: {} };
        render(tree());
        const button = screen.getByRole('button', { name: 'Export CSV' });
        expect(document.getElementById(button.getAttribute('aria-describedby')!)).toBe(screen.getByRole('status'));
        click('Export CSV');
        await screen.findByRole('alert');
        expect(document.getElementById(button.getAttribute('aria-describedby')!)).toBe(screen.getByRole('alert'));
    });
});

describe('the Dutch strings', () => {
    const keys = (obj: Record<string, string>) => Object.keys(obj).sort();
    const en = (commonEn as any).RESPONSE_EXPORT as Record<string, string>;
    const nl = (commonNl as any).RESPONSE_EXPORT as Record<string, string>;

    it('cover every English key, with the same placeholders', () => {
        expect(keys(nl)).toEqual(keys(en));
        for (const key of Object.keys(en)) {
            expect(nl[key].trim()).not.toBe('');
            expect(nl[key].match(/{{\w+}}/g) ?? []).toEqual(en[key].match(/{{\w+}}/g) ?? []);
        }
    });
});

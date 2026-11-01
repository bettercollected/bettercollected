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
    statusError: any;
    statusOptions: any[];
    downloadError: any;
    starts: any[];
    downloads: any[];
    discards: any[];
    discardError: any;
    saved: Array<{ blob: Blob; name: string }>;
} = { started: undefined, startError: undefined, mine: [], status: undefined, statusError: undefined, statusOptions: [], downloadError: undefined, starts: [], downloads: [], discards: [], discardError: undefined, saved: [] };

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
            return { data: options?.skip ? undefined : server.status, error: options?.skip ? undefined : server.statusError, refetch: () => ({ unwrap: async () => server.status }) };
        },
        useDiscardResponseExportMutation: () => [
            (arg: any) => ({
                unwrap: async () => {
                    server.discards.push(arg);
                    if (server.discardError) throw server.discardError;
                    return null;
                }
            })
        ],
        useDownloadResponseExportMutation: () => [
            (arg: any) => ({
                unwrap: async () => {
                    server.downloads.push(arg);
                    if (server.downloadError) {
                        const failure = server.downloadError;
                        if (failure.once) server.downloadError = undefined;
                        throw failure;
                    }
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
    window.localStorage.clear();
    Object.assign(server, { started: undefined, startError: undefined, mine: [], status: undefined, statusError: undefined, statusOptions: [], downloadError: undefined, starts: [], downloads: [], discards: [], discardError: undefined, saved: [] });
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

    it('holds what the list shows: its filters go with the request too', async () => {
        server.started = { kind: 'file', blob: new Blob(['a']), mediaType: 'text/csv' };
        const filters = { submittedFrom: '2026-10-01T00:00:00.000Z', respondent: 'known' as const, formVersion: [2], status: ['pending'] };
        render(tree({ filters }));
        click('Export matching responses');
        await waitFor(() => expect(server.starts).toHaveLength(1));
        expect(server.starts[0]).toEqual({ workspaceId: 'ws-1', formId: 'form-1', ...filters });
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
        expect(screen.getByText(/as often as you like/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Export CSV' })).not.toBeDisabled();
        // a ready export is not polled
        expect(lastStatusQuery().options.pollingInterval).toBe(0);

        click('Download');
        await waitFor(() => expect(server.saved).toHaveLength(1));
        // the link used is the one of a fresh status read
        expect(server.downloads).toEqual([{ downloadUrl: '/workspaces/ws-1/forms/form-1/exports/exp-1/download?token=1.abc' }]);
        expect(server.saved[0].name).toBe('Colours.csv');
        // the file stays, for as long as the server says: the button stays for another download
        expect(await screen.findByText(/The file stays on our servers until/)).toBeInTheDocument();
        // the retention sentence is said once
        expect(screen.queryByText(/as often as you like/)).toBeNull();
        expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument();
        click('Download');
        await waitFor(() => expect(server.saved).toHaveLength(2));
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
        ['failed', 'too_many_rows', 'more responses than one export can hold'],
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
        [{ status: 413, data: { code: 'too_many_rows' } }, 'more responses than one export can hold'],
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

describe('when following or fetching goes wrong', () => {
    it.each([
        [403, 'no longer export'],
        [404, 'no longer available']
    ])('stops following an export the poll is refused with %s', async (status, words) => {
        server.started = { kind: 'job', export: job() };
        const { rerender } = render(tree());
        click('Export CSV');
        await screen.findByRole('status');
        server.statusError = { status, data: {} };
        rerender(tree());
        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent(words);
        // no longer asked about: the poll is skipped
        expect(lastStatusQuery().options.skip).toBe(true);
        expect(screen.getByRole('button', { name: 'Export CSV' })).not.toBeDisabled();
    });

    it('keeps the Download button after a failed download of a file that is still there', async () => {
        server.mine = [ready()];
        server.status = ready();
        server.downloadError = { status: 500, data: {}, once: true };
        render(tree());
        await screen.findByText('Your export is ready.');
        click('Download');
        expect(await screen.findByText(/did not work/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument();
        click('Download');
        await waitFor(() => expect(server.saved).toHaveLength(1));
    });

    it('picks an export up again after the person dismisses a refusal', async () => {
        server.mine = [ready()];
        server.status = ready();
        server.downloadError = { status: 410, data: { code: 'export_gone' } };
        const { rerender } = render(tree());
        await screen.findByText('Your export is ready.');
        click('Download');
        expect(await screen.findByRole('alert')).toHaveTextContent('no longer available');
        // a new export of theirs is ready by now
        server.downloadError = undefined;
        server.mine = [ready({ id: 'exp-2' })];
        server.status = ready({ id: 'exp-2' });
        click('Dismiss');
        rerender(tree());
        expect(await screen.findByText('Your export is ready.')).toBeInTheDocument();
        expect(lastStatusQuery().arg.exportId).toBe('exp-2');
    });

    it('follows a ready export when a new one is refused for it', async () => {
        server.startError = { status: 409, data: { code: 'export_ready' } };
        render(tree());
        server.mine = [ready()];
        server.status = ready();
        click('Export CSV');
        expect(await screen.findByText('Your export is ready.')).toBeInTheDocument();
    });

    it.each([
        [{ status: 409, data: { code: 'export_ready' } }, 'delete the file to start a new one'],
        [{ status: 429, data: { code: 'workspace_busy' } }, 'Several exports of this workspace'],
        // too many exports of one person running at once: not the "exported too often" message
        [{ status: 429, data: { code: 'export_busy' } }, 'You already have exports of this workspace running']
    ])('names the refusal %j', async (error, words) => {
        server.startError = error;
        render(tree());
        click('Export CSV');
        expect(await screen.findByRole('alert')).toHaveTextContent(words);
    });

    it("says what the too-many-responses refusal offers: the list's filters or a search", async () => {
        server.startError = { status: 413, data: { code: 'too_many_rows' } };
        render(tree());
        click('Export CSV');
        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent('100,000');
        expect(alert).toHaveTextContent('Narrow the list with the filters or a search');
    });
});

describe('deleting a ready file', () => {
    it('deletes it on request, says so and frees the button for a new export', async () => {
        server.mine = [ready()];
        server.status = ready();
        const { rerender } = render(tree());
        await screen.findByText('Your export is ready.');
        click('Delete the file');
        expect(await screen.findByText(/The file was deleted from our servers/)).toBeInTheDocument();
        expect(server.discards).toEqual([{ workspaceId: 'ws-1', formId: 'form-1', exportId: 'exp-1' }]);
        expect(screen.queryByRole('button', { name: 'Download' })).toBeNull();
        expect(screen.getByRole('button', { name: 'Export CSV' })).not.toBeDisabled();
        // the export is no longer followed
        server.mine = [];
        rerender(tree());
        expect(lastStatusQuery().options.skip).toBe(true);
    });

    it('leaves the file where it was when deleting fails, and lets the person try again', async () => {
        server.mine = [ready()];
        server.status = ready();
        server.discardError = { status: 500, data: {} };
        render(tree());
        await screen.findByText('Your export is ready.');
        click('Delete the file');
        expect(await screen.findByText(/did not work/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument();
        server.discardError = undefined;
        click('Delete the file');
        expect(await screen.findByText(/The file was deleted from our servers/)).toBeInTheDocument();
        expect(server.discards).toHaveLength(2);
    });

    it('says a file that is already gone is gone', async () => {
        server.mine = [ready()];
        server.status = ready();
        server.discardError = { status: 404, data: {} };
        render(tree());
        await screen.findByText('Your export is ready.');
        click('Delete the file');
        expect(await screen.findByRole('alert')).toHaveTextContent('no longer available');
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


describe('the format', () => {
    const radio = (name: string) => screen.getByRole('radio', { name });

    it('is a radio group of CSV, Excel and JSON, CSV by default, named for screen readers', () => {
        render(tree());
        const group = screen.getByRole('radiogroup', { name: 'File format' });
        expect(group).toBeInTheDocument();
        expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-checked'))).toEqual(['true', 'false', 'false']);
        expect(screen.getAllByRole('radio').map((r) => r.id)).toEqual(['response-export-format-csv', 'response-export-format-xlsx', 'response-export-format-json']);
        expect(radio('CSV')).toBeChecked();
        // each option has its visible label
        expect(screen.getByText('Excel')).toBeInTheDocument();
        expect(screen.getByText('JSON')).toBeInTheDocument();
    });

    it('asks for an Excel workbook and saves it as one', async () => {
        server.started = { kind: 'file', blob: new Blob(['PK']), mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' };
        render(tree());
        fireEvent.click(radio('Excel'));
        expect(screen.getByRole('button', { name: 'Export Excel' })).toBeInTheDocument();
        click('Export Excel');
        await waitFor(() => expect(server.saved).toHaveLength(1));
        expect(server.starts).toEqual([{ workspaceId: 'ws-1', formId: 'form-1', format: 'xlsx' }]);
        expect(server.saved[0].name).toBe('Colours.xlsx');
    });

    it('asks for JSON and saves it as JSON, with the list’s search and filters', async () => {
        server.started = { kind: 'file', blob: new Blob(['{}']), mediaType: 'application/json; charset=utf-8' };
        render(tree({ search: 'sita@example.org', filters: { respondent: 'known' as const } }));
        fireEvent.click(radio('JSON'));
        click('Export matching responses');
        await waitFor(() => expect(server.saved).toHaveLength(1));
        expect(server.starts).toEqual([{ workspaceId: 'ws-1', formId: 'form-1', search: 'sita@example.org', respondent: 'known', format: 'json' }]);
        expect(server.saved[0].name).toBe('Colours.json');
    });

    it('a large export in another format is followed and downloaded like any other', async () => {
        server.started = { kind: 'job', export: job({ format: 'xlsx', fileName: 'Colours.xlsx' }) };
        server.status = ready({ format: 'xlsx', fileName: 'Colours.xlsx' });
        render(tree());
        fireEvent.click(radio('Excel'));
        click('Export Excel');
        expect(await screen.findByText('Your export is ready.')).toBeInTheDocument();
        click('Download');
        await waitFor(() => expect(server.saved).toHaveLength(1));
        expect(server.saved[0].name).toBe('Colours.xlsx');
        expect(server.starts[0]).toMatchObject({ format: 'xlsx' });
    });

    it('is remembered in this browser, and a store that cannot be read is CSV', () => {
        const first = render(tree());
        fireEvent.click(radio('JSON'));
        expect(window.localStorage.getItem('bc.responseExportFormat')).toBe('json');
        first.unmount();
        const second = render(tree());
        expect(radio('JSON')).toBeChecked();
        second.unmount();
        // nonsense in the store, or no store at all
        window.localStorage.setItem('bc.responseExportFormat', 'pdf');
        const third = render(tree());
        expect(radio('CSV')).toBeChecked();
        third.unmount();
        const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        render(tree());
        expect(radio('CSV')).toBeChecked();
        fireEvent.click(radio('Excel'));
        expect(radio('Excel')).toBeChecked();
        get.mockRestore();
        set.mockRestore();
    });

    it('cannot be changed while an export is being prepared', async () => {
        server.started = { kind: 'job', export: job() };
        render(tree());
        click('Export CSV');
        await screen.findByRole('status');
        screen.getAllByRole('radio').forEach((r) => expect(r).toBeDisabled());
    });

    it('says when a form has too many columns for an Excel sheet', async () => {
        server.startError = { status: 422, data: { code: 'too_many_columns' } };
        render(tree());
        fireEvent.click(radio('Excel'));
        click('Export Excel');
        expect(await screen.findByRole('alert')).toHaveTextContent('more columns than an Excel sheet can hold');
    });

    it('speaks Dutch', () => {
        const nl = (commonNl as any).RESPONSE_EXPORT;
        for (const key of ['BUTTON', 'FORMAT', 'FORMAT_CSV', 'FORMAT_XLSX', 'FORMAT_JSON', 'ERROR_TOO_MANY_COLUMNS']) {
            expect(nl[key], key).toBeTruthy();
            expect((commonEn as any).RESPONSE_EXPORT[key], key).toBeTruthy();
        }
        expect(nl.BUTTON).toContain('{{format}}');
    });
});

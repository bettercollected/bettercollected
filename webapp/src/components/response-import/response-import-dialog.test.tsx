import React from 'react';

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import type { ResponseImportDto } from '@app/store/workspaces/api';
import { workspacesApi } from '@app/store/workspaces/api';

import enCommon from '../../../public/locales/en/common.json';
import nlCommon from '../../../public/locales/nl/common.json';
import ImportedBadge from './imported-badge';
import ResponseImportDialog from './response-import-dialog';

const en = (enCommon as any).RESPONSE_IMPORT;
const nl = (nlCommon as any).RESPONSE_IMPORT;

const BASE: ResponseImportDto = {
    id: 'imp1',
    formId: 'form1',
    status: 'uploaded',
    fileSize: 120,
    encoding: 'utf-8',
    separator: ',',
    rowCount: 3,
    columnCount: 3,
    headers: ['Full name', 'Age', 'Responder ID'],
    mapping: { '0': 'q:name', '1': 'q:age' },
    options: {},
    problems: [],
    problemCounts: {},
    problemsTruncated: false,
    notes: [{ column: 2, code: 'responder_ignored' }],
    progress: 0,
    targets: [
        { key: 'responder', label: 'Responder ID', kind: 'responder', status: 'ignored', reason: 'responder_ignored' },
        { key: 'q:name', label: 'Full name', kind: 'question', status: 'ok', fieldId: 'name', type: 'short_text' },
        { key: 'q:age', label: 'Age', kind: 'question', status: 'ok', fieldId: 'age', type: 'number' },
        { key: 'internal:note', label: 'Staff note', kind: 'internal', status: 'ok', fieldId: 'note', type: 'short_text' },
        { key: 'submitted_at', label: 'Submitted at (UTC, ISO 8601)', kind: 'meta', status: 'ok' }
    ]
};

function json(status: number, body: unknown, headers: Record<string, string> = {}) {
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });
}

type Call = { method: string; path: string; type: string | null; body: string };
let calls: Call[] = [];
let routes: Record<string, (call: Call) => Response> = {};

function install() {
    calls = [];
    vi.stubGlobal(
        'fetch',
        vi.fn(async (request: Request) => {
            const url = new URL(request.url);
            const path = url.pathname.replace(/^.*\/forms\/form1\/imports/, '');
            const call: Call = { method: request.method, path, type: request.headers.get('content-type'), body: await request.clone().text() };
            calls.push(call);
            const route = routes[`${request.method} ${path}`] ?? routes[`${request.method} *`];
            return route ? route(call) : json(404, {});
        })
    );
}

beforeEach(() => {
    routes = { 'GET ': () => json(200, []) };
    install();
});

afterEach(async () => {
    cleanup();
    vi.unstubAllGlobals();
    store.dispatch(workspacesApi.util.resetApiState());
    await i18n.changeLanguage('en');
});

function open() {
    return render(
        <ReduxProvider store={store}>
            <ResponseImportDialog open onOpenChange={() => undefined} workspaceId="ws1" formId="form1" />
        </ReduxProvider>
    );
}

async function upload(name = 'people.csv', content = 'Full name,Age,Responder ID\nAda,36,x\n') {
    const input = await screen.findByTestId('ri-file-input');
    fireEvent.change(input, { target: { files: [new File([content], name, { type: 'text/csv' })] } });
}

describe('the import dialog', () => {
    it('sends the file itself as the body, not a form, and shows the columns to match', async () => {
        routes['POST '] = () => json(201, BASE);
        open();
        await upload();
        expect(await screen.findByText(en.MAP_TITLE)).toBeInTheDocument();
        const post = calls.find((c) => c.method === 'POST')!;
        expect(post.type).toBe('text/csv');
        expect(post.body).toContain('Ada,36');
        // the suggested mapping is preselected; a column the export writes but an import leaves alone says why
        expect(screen.getByLabelText(`${en.TARGET_HEADER}: Full name`)).toHaveValue('q:name');
        expect(screen.getByLabelText(`${en.TARGET_HEADER}: Responder ID`)).toHaveValue('');
        expect(screen.getByText(en.NOTE_responder_ignored)).toBeInTheDocument();
        // staff-only questions are named as such, the ignored target is not offered
        const options = within(screen.getByLabelText(`${en.TARGET_HEADER}: Responder ID`)).getAllByRole('option');
        expect(options.map((o) => o.textContent)).toContain('Staff note (staff only)');
        expect(options.map((o) => o.textContent)).not.toContain('Responder ID');
    });

    it('offers a question once: it is taken from the other columns', async () => {
        routes['POST '] = () => json(201, BASE);
        open();
        await upload();
        await screen.findByText(en.MAP_TITLE);
        const other = within(screen.getByLabelText(`${en.TARGET_HEADER}: Age`)).getByRole('option', { name: 'Full name' }) as HTMLOptionElement;
        expect(other.disabled).toBe(true);
        const free = within(screen.getByLabelText(`${en.TARGET_HEADER}: Responder ID`)).getByRole('option', { name: 'Staff note (staff only)' }) as HTMLOptionElement;
        expect(free.disabled).toBe(false);
    });

    it('does not check a mapping that fills no question', async () => {
        routes['POST '] = () => json(201, { ...BASE, mapping: {} });
        open();
        await upload();
        await screen.findByText(en.MAP_TITLE);
        expect(screen.getByRole('button', { name: en.CHECK })).toBeDisabled();
    });

    it('checks, lists the problems by row and place without any value, and imports only after the confirmation', async () => {
        routes['POST '] = () => json(201, BASE);
        routes['POST /imp1/check'] = () => json(202, { ...BASE, status: 'checking', mode: 'check' });
        const checked: ResponseImportDto = {
            ...BASE,
            status: 'checked',
            rowsValid: 2,
            rowsInvalid: 1,
            problems: [
                { row: 3, column: 1, field: 'age', code: 'too_large' },
                { row: 4, column: null, field: 'name', code: 'required' },
                { row: 5, column: 0, field: 'name', code: 'a_rule_from_a_newer_server' }
            ],
            problemCounts: { too_large: 1, required: 1, a_rule_from_a_newer_server: 1 }
        };
        routes['GET /imp1'] = () => json(200, checked);
        routes['POST /imp1/run'] = () => json(202, { ...BASE, status: 'queued', mode: 'import' });
        open();
        await upload();
        fireEvent.click(await screen.findByRole('button', { name: en.CHECK }));
        expect(await screen.findByText(en.CHECK_TITLE)).toBeInTheDocument();
        const request = JSON.parse(calls.find((c) => c.path === '/imp1/check')!.body);
        expect(request).toEqual({ mapping: { '0': 'q:name', '1': 'q:age' }, skipInvalidRows: false });
        const table = screen.getByRole('table', { name: '' });
        expect(within(table).getByText('Above the highest value')).toBeInTheDocument();
        expect(within(table).getByText('An answer is required')).toBeInTheDocument();
        expect(within(table).getByText('Not accepted (a_rule_from_a_newer_server)')).toBeInTheDocument();
        // where: the question, then the file's own heading
        expect(within(table).getByText('Age')).toBeInTheDocument();
        // a problem of the row as a whole names its question; one in a column whose heading is the question says it once
        expect(within(table).getAllByText('Full name')).toHaveLength(2);
        // one row has a problem and skipping was not chosen: nothing can be imported yet
        expect(screen.getByRole('button', { name: /Import 2 valid rows|2 valid rows/ })).toBeDisabled();
    });

    it('imports the valid rows when skipping was chosen, once confirmed, and shows the result and the undo', async () => {
        routes['POST '] = () => json(201, BASE);
        routes['POST /imp1/check'] = () => json(202, { ...BASE, status: 'checking', mode: 'check' });
        routes['GET /imp1'] = () => json(200, { ...BASE, status: 'checked', rowsValid: 2, rowsInvalid: 1, problems: [{ row: 3, column: 1, field: 'age', code: 'too_large' }], problemCounts: { too_large: 1 } });
        routes['POST /imp1/run'] = () => json(202, { ...BASE, status: 'queued', mode: 'import' });
        open();
        await upload();
        fireEvent.click(await screen.findByLabelText(new RegExp(en.SKIP_INVALID.slice(0, 20))));
        fireEvent.click(screen.getByRole('button', { name: en.CHECK }));
        await screen.findByText(en.CHECK_TITLE);
        const run = screen.getByRole('button', { name: /2 valid rows/ });
        expect(run).toBeDisabled();
        fireEvent.click(screen.getByRole('checkbox', { name: new RegExp(en.CONFIRM.slice(0, 25)) }));
        expect(run).toBeEnabled();
        routes['GET /imp1'] = () => json(200, { ...BASE, status: 'completed', rowsImported: 2, rowsSkipped: 1, rowsValid: 2, rowsInvalid: 1, progress: 3, canRollback: true, rollbackUntil: '2026-11-15T10:00:00Z', targets: undefined, headers: [] });
        fireEvent.click(run);
        expect(await screen.findByText('2 responses were imported.')).toBeInTheDocument();
        expect(JSON.parse(calls.find((c) => c.path === '/imp1/run')!.body)).toEqual({ mapping: { '0': 'q:name', '1': 'q:age' }, skipInvalidRows: true, confirmedLawfulBasis: true });
        expect(screen.getByText('1 row was skipped.')).toBeInTheDocument();
        expect(screen.getByText(en.DONE_NOTHING_FIRED)).toBeInTheDocument();
        // undo asks first, then deletes
        routes['POST /imp1/rollback'] = () => json(200, { ...BASE, status: 'rolled_back', rolledBackCount: 2, rowsImported: 2, targets: undefined, headers: [] });
        fireEvent.click(screen.getByRole('button', { name: en.UNDO }));
        expect(calls.some((c) => c.path === '/imp1/rollback')).toBe(false);
        fireEvent.click(screen.getByRole('button', { name: en.UNDO_YES }));
        expect(await screen.findByText('The import was undone: 2 responses were deleted.')).toBeInTheDocument();
    });

    it('says a failed import stored nothing and why', async () => {
        routes['POST '] = () => json(201, BASE);
        routes['POST /imp1/check'] = () => json(202, { ...BASE, status: 'checking', mode: 'check' });
        routes['GET /imp1'] = () => json(200, { ...BASE, status: 'failed', errorCode: 'form_full', targets: undefined });
        open();
        await upload();
        fireEvent.click(await screen.findByRole('button', { name: en.CHECK }));
        expect(await screen.findByText(en.FAILED_TITLE)).toBeInTheDocument();
        expect(screen.getByText(en.ERROR_form_full)).toBeInTheDocument();
        expect(screen.getByText(en.FAILED_NOTHING_STORED)).toBeInTheDocument();
    });

    it('shows the refusal of an upload in words, never the code', async () => {
        routes['POST '] = () => json(415, { code: 'unsupported_format', message: 'x' });
        open();
        await upload('sheet.xlsx', 'PK');
        expect(await screen.findByText(en.ERROR_unsupported_format)).toBeInTheDocument();
        expect(screen.queryByText(/unsupported_format/)).toBeNull();
    });

    it('refuses a file over the limit before sending it', async () => {
        open();
        const input = await screen.findByTestId('ri-file-input');
        const big = new File(['x'], 'big.csv', { type: 'text/csv' });
        Object.defineProperty(big, 'size', { value: 6 * 1024 * 1024 });
        fireEvent.change(input, { target: { files: [big] } });
        expect(await screen.findByText('This file is too large (at most 5 MB).')).toBeInTheDocument();
        expect(calls.some((c) => c.method === 'POST')).toBe(false);
    });

    it('is in Dutch for the dashboard, formal', async () => {
        await i18n.changeLanguage('nl');
        routes['POST '] = () => json(201, BASE);
        open();
        expect((await screen.findAllByText(nl.TITLE)).length).toBeGreaterThan(0);
        await upload();
        expect(await screen.findByText(nl.MAP_TITLE)).toBeInTheDocument();
        expect(screen.getByText(nl.NOTE_responder_ignored)).toBeInTheDocument();
        expect(nl.MAP_HELP).toContain('uw');
    });

    it('adopts an import that is waiting after a reload', async () => {
        routes['GET '] = () => json(200, [{ ...BASE, byMe: true, targets: undefined }]);
        routes['GET /imp1'] = () => json(200, { ...BASE, byMe: true });
        open();
        expect(await screen.findByText(en.MAP_TITLE)).toBeInTheDocument();
    });
});

describe('the imported mark', () => {
    it('is a labelled badge', () => {
        render(<ImportedBadge />);
        expect(screen.getByText(en.IMPORTED_BADGE)).toBeInTheDocument();
    });
});

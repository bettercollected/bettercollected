import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import type { OpenFormulierenImport } from '@app/store/redux/open-formulieren-import-api';
import { openFormulierenImportApi } from '@app/store/redux/open-formulieren-import-api';
import { store } from '@app/store/store';
import { UPLOAD_ERROR_CODES } from '@app/utils/open-formulieren-import';

import enBuilder from '../../../public/locales/en/builder.json';
import nlBuilder from '../../../public/locales/nl/builder.json';
import ImportOpenFormulierenDialog from './import-dialog';
import ImportReport, { ImportReportView } from './import-report';
import { NeedsReviewBadge, NeedsReviewBanner, needsOpenFormulierenReview, useShowNeedsReviewBanner } from './needs-review';

const en = (enBuilder as any).OPEN_FORMULIEREN_IMPORT;
const nl = (nlBuilder as any).OPEN_FORMULIEREN_IMPORT;

const push = vi.fn();
vi.mock('next-nprogress-bar', () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));

const IMPORT: OpenFormulierenImport = {
    id: 'imp1',
    formId: 'form1',
    status: 'completed',
    needsReview: true,
    sourceKind: 'open_formulieren',
    sourceVersion: '4.0.6',
    fileName: 'sample.zip',
    sizeBytes: 20480,
    createdAt: '2026-10-27T10:00:00Z',
    summary: { pages: 3, fields: 18, logicRules: 2, repeatingGroups: 1, dropped: 2, flagged: 1 },
    report: {
        truncated: false,
        items: [
            { code: 'dropped', kind: 'component', key: 'signature', label: 'Signature', reason: 'unsupported_component_type', severity: 'warning', step: 2, detail: { componentType: 'signature' } },
            { code: 'dropped', kind: 'logic', key: 'rule-1', label: 'Hide the car questions', reason: 'action_not_supported', severity: 'warning', detail: { actionType: 'disable-next' } },
            { code: 'flagged', kind: 'component', key: 'bsn', label: 'National identity number', reason: 'national_identity_number', severity: 'warning', flag: 'national_identity_number', step: 0 },
            { code: 'changed', kind: 'component', key: 'when', label: 'Date and time', reason: 'datetime_split', severity: 'info', step: 1 }
        ]
    }
};

function json(status: number, body: unknown) {
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function wrap(node: React.ReactElement) {
    return <ReduxProvider store={store}>{node}</ReduxProvider>;
}

afterEach(async () => {
    vi.unstubAllGlobals();
    push.mockClear();
    store.dispatch(openFormulierenImportApi.util.resetApiState());
    await i18n.changeLanguage('en');
});

describe('the import report', () => {
    it('shows the summary and one sentence per item, grouped by what happened', () => {
        render(wrap(<ImportReportView data={IMPORT} workspaceId="ws1" workspaceName="acme" />));
        const summary = screen.getByLabelText(en.REPORT.SUMMARY_LABEL);
        expect(within(summary).getByText('3 pages')).toBeInTheDocument();
        expect(within(summary).getByText('18 questions')).toBeInTheDocument();
        expect(within(summary).getByText('2 rules for showing or hiding questions')).toBeInTheDocument();
        expect(within(summary).getByText('2 items not imported')).toBeInTheDocument();
        expect(within(summary).getByText('1 item to check')).toBeInTheDocument();

        expect(screen.getByText('This question type (“signature”) is not supported, so it was left out.')).toBeInTheDocument();
        expect(screen.getByText('A rule does something we do not support (“disable-next”), so it was left out.')).toBeInTheDocument();
        expect(screen.getByText('This date and time question became two questions: one for the date and one for the time.')).toBeInTheDocument();
        // the page of an item is 1-based
        expect(screen.getByText('Page 3')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /^To check/ })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /^Not imported/ })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /^Imported in a different way/ })).toBeInTheDocument();
    });

    it('flags the national identity number prominently, naming the questions', () => {
        render(wrap(<ImportReportView data={IMPORT} workspaceId="ws1" workspaceName="acme" />));
        const flag = screen.getByRole('region', { name: 'National identity number: check you need it.' });
        expect(within(flag).getByRole('heading', { level: 2 })).toHaveTextContent('National identity number: check you need it.');
        expect(within(flag).getByText('National identity number', { selector: 'li' })).toBeInTheDocument();
        // it comes before the summary and the list
        expect(flag.compareDocumentPosition(screen.getByLabelText(en.REPORT.SUMMARY_LABEL)) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it('has no flag when the import has none', () => {
        const data = { ...IMPORT, report: { truncated: false, items: IMPORT.report.items.filter((item) => !item.flag) } };
        render(wrap(<ImportReportView data={data} workspaceId="ws1" workspaceName="acme" />));
        expect(screen.queryByText('National identity number: check you need it.')).toBeNull();
    });

    it('uses a generic sentence for a reason it does not know', () => {
        const data = { ...IMPORT, report: { truncated: false, items: [{ code: 'dropped', kind: 'component', key: 'x', label: 'Mystery', reason: 'from_a_newer_server', severity: 'warning' }] } };
        render(wrap(<ImportReportView data={data} workspaceId="ws1" workspaceName="acme" />));
        expect(screen.getByText('Mystery')).toBeInTheDocument();
        expect(screen.getByText(en.REASON_FALLBACK.dropped)).toBeInTheDocument();
        expect(screen.queryByText(/from_a_newer_server/)).toBeNull();
    });

    it('does not show a bare placeholder when the detail a sentence needs is missing', () => {
        const data = { ...IMPORT, report: { truncated: false, items: [{ code: 'dropped', kind: 'component', reason: 'unsupported_component_type', severity: 'warning' }] } };
        const { container } = render(wrap(<ImportReportView data={data} workspaceId="ws1" workspaceName="acme" />));
        expect(container.textContent).toContain('(“unknown”)');
        expect(container.textContent).not.toContain('{{');
    });

    it('renders labels and details as text, never as HTML', () => {
        const hostile = '<img src=x onerror="window.__pwned = true">';
        const data = {
            ...IMPORT,
            fileName: hostile,
            report: {
                truncated: false,
                items: [
                    { code: 'dropped', kind: 'component', key: hostile, label: hostile, reason: 'unsupported_component_type', severity: 'warning', detail: { componentType: hostile } },
                    { code: 'flagged', kind: 'component', label: hostile, reason: 'national_identity_number', severity: 'warning', flag: 'national_identity_number' }
                ]
            }
        };
        const { container } = render(wrap(<ImportReportView data={data} workspaceId="ws1" workspaceName="acme" />));
        expect(container.querySelector('img')).toBeNull();
        expect(container.querySelector('[onerror]')).toBeNull();
        expect(screen.getAllByText(hostile, { exact: false }).length).toBeGreaterThan(0);
        expect((window as any).__pwned).toBeUndefined();
    });

    it('offers the editor and marks the import as reviewed', async () => {
        const fetchMock = vi.fn(async () => json(200, { ...IMPORT, needsReview: false }));
        vi.stubGlobal('fetch', fetchMock);
        render(wrap(<ImportReportView data={IMPORT} workspaceId="ws1" workspaceName="acme" />));
        expect(screen.getByRole('link', { name: 'Open in editor' })).toHaveAttribute('href', '/acme/dashboard/forms/form1/edit');
        fireEvent.click(screen.getByRole('button', { name: 'Mark as reviewed' }));
        await waitFor(() => expect(fetchMock).toHaveBeenCalled());
        const request = (fetchMock.mock.calls[0] as any[])[0] as Request;
        expect(request.method).toBe('POST');
        expect(request.url).toContain('/workspaces/ws1/open-formulieren-imports/imp1/review');
        expect(await request.clone().json()).toEqual({ reviewed: true });
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Marked as reviewed.'));
    });

    it('says when the report was cut at 500 items', () => {
        render(wrap(<ImportReportView data={{ ...IMPORT, report: { ...IMPORT.report, truncated: true } }} workspaceId="ws1" workspaceName="acme" />));
        expect(screen.getByText(en.REPORT.TRUNCATED)).toBeInTheDocument();
    });

    it('speaks Dutch', async () => {
        await i18n.changeLanguage('nl');
        render(wrap(<ImportReportView data={IMPORT} workspaceId="ws1" workspaceName="acme" />));
        expect(screen.getByRole('heading', { level: 2, name: nl.REPORT.ID_TITLE })).toBeInTheDocument();
        expect(screen.getByText('Dit vraagtype (“signature”) wordt niet ondersteund en is weggelaten.')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: nl.REPORT.OPEN_EDITOR })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: nl.REPORT.MARK_REVIEWED })).toBeInTheDocument();
    });

    it('offers to mark it as needing review again once reviewed', () => {
        render(wrap(<ImportReportView data={{ ...IMPORT, needsReview: false }} workspaceId="ws1" workspaceName="acme" />));
        expect(screen.getByText(en.REPORT.REVIEWED_NOTE)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Needs review again' })).toBeInTheDocument();
    });

    it('loads the report of an import from the server', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => json(200, IMPORT))
        );
        await act(async () => {
            render(wrap(<ImportReport workspaceId="ws1" workspaceName="acme" importId="imp1" />));
        });
        expect(await screen.findByText('Your draft form is ready')).toBeInTheDocument();
    });

    it('says so when the import cannot be found', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => json(404, { code: 'import_not_found', message: 'x' }))
        );
        await act(async () => {
            render(wrap(<ImportReport workspaceId="ws1" workspaceName="acme" importId="nope" />));
        });
        expect(await screen.findByRole('alert')).toHaveTextContent(en.ERROR.import_not_found);
    });
});

describe('the upload dialog', () => {
    const zip = (name = 'export.zip', size = 1024) => {
        const file = new File(['x'], name, { type: 'application/zip' });
        Object.defineProperty(file, 'size', { value: size });
        return file;
    };

    async function chooseAndImport(file: File) {
        fireEvent.change(screen.getByTestId('oof-file-input'), { target: { files: [file] } });
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Import' }));
        });
    }

    function open() {
        return render(wrap(<ImportOpenFormulierenDialog open onOpenChange={vi.fn()} workspaceId="ws1" workspaceName="acme" />));
    }

    it('shows the size limit and keeps Import off until a file is chosen', () => {
        open();
        expect(screen.getByText('One form per zip file, up to 5 MB')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled();
        fireEvent.change(screen.getByTestId('oof-file-input'), { target: { files: [zip()] } });
        expect(screen.getByRole('button', { name: 'Import' })).toBeEnabled();
        expect(screen.getByText('export.zip')).toBeInTheDocument();
    });

    it('refuses a file over 5 MiB without sending it', async () => {
        const fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);
        open();
        fireEvent.change(screen.getByTestId('oof-file-input'), { target: { files: [zip('big.zip', 6 * 1024 * 1024)] } });
        expect(screen.getByRole('alert')).toHaveTextContent('The limit is 5 MB');
        expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled();
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it('sends the file as multipart "file" and opens the report on success', async () => {
        const fetchMock = vi.fn(async () => json(201, IMPORT));
        vi.stubGlobal('fetch', fetchMock);
        const onOpenChange = vi.fn();
        render(wrap(<ImportOpenFormulierenDialog open onOpenChange={onOpenChange} workspaceId="ws1" workspaceName="acme" />));
        await chooseAndImport(zip());
        const request = (fetchMock.mock.calls[0] as any[])[0] as Request;
        expect(request.method).toBe('POST');
        expect(request.url).toContain('/workspaces/ws1/open-formulieren-imports');
        const form = await request.clone().formData();
        // the one multipart field is called "file" and holds the zip's bytes
        expect(await (form.get('file') as Blob).text()).toBe('x');
        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
        });
        await waitFor(() => expect(push).toHaveBeenCalledWith('/acme/dashboard/forms/import/open-formulieren/imp1'));
        expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('shows the report straight from the upload answer, without asking again', async () => {
        const fetchMock = vi.fn(async () => json(201, IMPORT));
        vi.stubGlobal('fetch', fetchMock);
        open();
        await chooseAndImport(zip());
        await waitFor(() => expect(push).toHaveBeenCalled());
        fetchMock.mockClear();
        await act(async () => {
            render(wrap(<ImportReport workspaceId="ws1" workspaceName="acme" importId="imp1" />));
        });
        expect(await screen.findByText('Your draft form is ready')).toBeInTheDocument();
        expect(screen.getByText('National identity number: check you need it.')).toBeInTheDocument();
        expect(fetchMock).not.toHaveBeenCalled();
    });

    const refusals: Record<string, { status: number; body: Record<string, unknown>; en: string; nl: string }> = {
        open_formulieren_off: { status: 410, body: {}, en: en.ERROR.open_formulieren_off, nl: nl.ERROR.open_formulieren_off },
        file_missing: { status: 400, body: {}, en: en.ERROR.file_missing, nl: nl.ERROR.file_missing },
        file_too_large: { status: 413, body: { maxBytes: 5242880 }, en: 'The limit is 5 MB', nl: 'De grens is 5 MB' },
        not_a_zip: { status: 400, body: {}, en: en.ERROR.not_a_zip, nl: nl.ERROR.not_a_zip },
        archive_unsafe: { status: 400, body: {}, en: en.ERROR.archive_unsafe, nl: nl.ERROR.archive_unsafe },
        archive_too_large: { status: 400, body: {}, en: en.ERROR.archive_too_large, nl: nl.ERROR.archive_too_large },
        archive_incomplete: { status: 400, body: { missing: ['forms.json', '_meta.json'] }, en: 'It is missing: forms.json, _meta.json.', nl: 'Er ontbreekt: forms.json, _meta.json.' },
        archive_json_invalid: { status: 400, body: { file: 'formSteps.json' }, en: 'the file “formSteps.json”', nl: 'het bestand “formSteps.json”' },
        archive_not_a_single_form: { status: 400, body: {}, en: en.ERROR.archive_not_a_single_form, nl: nl.ERROR.archive_not_a_single_form },
        open_formulieren_version_unknown: { status: 400, body: {}, en: en.ERROR.open_formulieren_version_unknown, nl: nl.ERROR.open_formulieren_version_unknown },
        open_formulieren_version_unsupported: {
            status: 400,
            body: { version: '4.1.2', supported: ['4.0'] },
            en: 'This file comes from Open Formulieren 4.1.2. We can only read exports from version 4.0.x.',
            nl: 'Dit bestand komt uit Open Formulieren 4.1.2. We kunnen alleen exports lezen uit versie 4.0.x.'
        },
        no_importable_fields: { status: 422, body: {}, en: en.ERROR.no_importable_fields, nl: nl.ERROR.no_importable_fields },
        archive_too_complex: { status: 422, body: {}, en: en.ERROR.archive_too_complex, nl: nl.ERROR.archive_too_complex },
        import_not_found: { status: 404, body: {}, en: en.ERROR.import_not_found, nl: nl.ERROR.import_not_found }
    };

    it('covers every error code of the contract', () => {
        expect(Object.keys(refusals).sort()).toEqual([...UPLOAD_ERROR_CODES].sort());
    });

    it.each(Object.entries(refusals))('explains "%s" in English', async (code, refusal) => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => json(refusal.status, { code, message: 'English fallback', ...refusal.body }))
        );
        open();
        await chooseAndImport(zip());
        const alert = await screen.findByText((_, node) => node?.tagName === 'P' && node.textContent?.includes(refusal.en) === true);
        expect(alert).toBeInTheDocument();
        expect(screen.getByRole('alert')).toContainElement(alert);
        expect(push).not.toHaveBeenCalled();
    });

    it.each(Object.entries(refusals))('explains "%s" in Dutch', async (code, refusal) => {
        await i18n.changeLanguage('nl');
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => json(refusal.status, { code, message: 'English fallback', ...refusal.body }))
        );
        open();
        fireEvent.change(screen.getByTestId('oof-file-input'), { target: { files: [zip()] } });
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: nl.DIALOG.IMPORT }));
        });
        expect(await screen.findByText((_, node) => node?.tagName === 'P' && node.textContent?.includes(refusal.nl) === true)).toBeInTheDocument();
    });

    it('lists why nothing could be imported', async () => {
        const reportItems = [{ code: 'dropped', kind: 'component', label: 'Signature', reason: 'unsupported_component_type', severity: 'warning', detail: { componentType: 'signature' } }];
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => json(422, { code: 'no_importable_fields', message: 'x', reportItems }))
        );
        open();
        await chooseAndImport(zip());
        expect(await screen.findByText(en.ERROR.no_importable_fields)).toBeInTheDocument();
        expect(screen.getByText('Signature')).toBeInTheDocument();
        expect(screen.getByText('This question type (“signature”) is not supported, so it was left out.')).toBeInTheDocument();
    });

    it('says "not allowed" for a 403 and a generic line when the network fails', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => json(403, { detail: 'Forbidden' }))
        );
        const { unmount } = open();
        await chooseAndImport(zip());
        expect(await screen.findByText(en.ERROR.forbidden)).toBeInTheDocument();
        unmount();
        store.dispatch(openFormulierenImportApi.util.resetApiState());
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => json(500, 'boom'))
        );
        open();
        await chooseAndImport(zip());
        expect(await screen.findByText(en.ERROR.upload_failed)).toBeInTheDocument();
    });
});

describe('the needs-review mark', () => {
    const marked = { needsReview: true, importSource: 'open_formulieren', importId: 'imp1' };

    it('shows the badge only for an imported form that needs review', () => {
        const { rerender } = render(<NeedsReviewBadge settings={marked} />);
        expect(screen.getByText('Needs review')).toBeInTheDocument();
        for (const settings of [undefined, null, {}, { ...marked, needsReview: false }, { ...marked, needsReview: null }, { ...marked, importSource: 'pdf' }, { needsReview: true }]) {
            rerender(<NeedsReviewBadge settings={settings as any} />);
            expect(screen.queryByText('Needs review')).toBeNull();
        }
        expect(needsOpenFormulierenReview(marked)).toBe(true);
    });

    it('shows the badge in Dutch', async () => {
        await i18n.changeLanguage('nl');
        render(<NeedsReviewBadge settings={marked} />);
        expect(screen.getByText(nl.NEEDS_REVIEW)).toBeInTheDocument();
    });

    it('links the banner to the report', () => {
        render(<NeedsReviewBanner importId="imp1" workspaceName="acme" />);
        expect(screen.getByRole('status')).toHaveTextContent('This form was imported from Open Formulieren and needs review.');
        expect(screen.getByRole('link', { name: 'See the import report' })).toHaveAttribute('href', '/acme/dashboard/forms/import/open-formulieren/imp1');
    });

    function Probe({ settings }: { settings: any }) {
        return <span data-testid="shown">{String(useShowNeedsReviewBanner(settings, 'ws1'))}</span>;
    }

    beforeEach(() => {
        store.dispatch(openFormulierenImportApi.util.resetApiState());
    });

    it('shows the banner for a marked form, and drops it once the report says reviewed', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => json(200, { ...IMPORT, needsReview: false }))
        );
        await act(async () => {
            render(wrap(<Probe settings={marked} />));
        });
        expect(screen.getByTestId('shown')).toHaveTextContent('true');
        await waitFor(() => expect(screen.getByTestId('shown')).toHaveTextContent('false'));
    });

    it('does not ask for a report when the form carries no mark', async () => {
        const fetchMock = vi.fn(async () => json(200, IMPORT));
        vi.stubGlobal('fetch', fetchMock);
        await act(async () => {
            render(wrap(<Probe settings={{ needsReview: false, importSource: 'open_formulieren', importId: 'imp1' }} />));
        });
        expect(screen.getByTestId('shown')).toHaveTextContent('false');
        expect(fetchMock).not.toHaveBeenCalled();
    });
});

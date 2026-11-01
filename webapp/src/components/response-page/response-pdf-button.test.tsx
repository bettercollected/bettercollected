import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import I18nProvider from '@app/shared/hocs/i18n-provider';

import commonEn from '../../../public/locales/en/common.json';
import commonNl from '../../../public/locales/nl/common.json';
import ResponsePdfButton, { pdfFailureMessage } from './response-pdf-button';

// The "server": what the PDF route answers, and every call made to it.
const server: { result: any; error: any; calls: any[]; saved: Array<{ blob: Blob; name: string }>; release?: () => void } = { result: undefined, error: undefined, calls: [], saved: [] };
const toast = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));
vi.mock('@app/utils/response-export', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, downloadBlob: (blob: Blob, name: string) => server.saved.push({ blob, name }) };
});
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useDownloadResponsePdfMutation: () => [
            (arg: any) => ({
                unwrap: async () => {
                    server.calls.push(arg);
                    if (server.release === undefined && server.error) throw server.error;
                    if (server.release) await new Promise<void>((resolve) => (server.release = resolve));
                    return server.result;
                }
            }),
            { isLoading: false }
        ]
    };
});

const tree = () => (
    <I18nProvider>
        <ResponsePdfButton workspaceId="ws-1" responseId="resp-1" formTitle="Summer meeting" />
    </I18nProvider>
);

beforeEach(() => {
    Object.assign(server, { result: { blob: new Blob(['%PDF']), fileName: 'Summer meeting - resp-1.pdf' }, error: undefined, calls: [], saved: [], release: undefined });
    toast.mockReset();
});

describe('Download PDF', () => {
    it('asks for the response in the reader’s language and time zone, and saves the file under the server’s name', async () => {
        render(tree());
        fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
        await waitFor(() => expect(server.saved).toHaveLength(1));
        expect(server.saved[0].name).toBe('Summer meeting - resp-1.pdf');
        expect(server.calls).toHaveLength(1);
        expect(server.calls[0]).toMatchObject({ workspaceId: 'ws-1', responseId: 'resp-1' });
        expect(typeof server.calls[0].lang).toBe('string');
        expect(server.calls[0].tz).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone);
        expect(toast).toHaveBeenCalledWith({ description: 'The PDF was downloaded.' });
    });

    it('names the file after the form when the server offers no name', async () => {
        server.result = { blob: new Blob(['%PDF']) };
        render(tree());
        fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
        await waitFor(() => expect(server.saved).toHaveLength(1));
        expect(server.saved[0].name).toBe('Summer meeting.pdf');
    });

    it('takes one click at a time and says it is working', async () => {
        server.release = () => undefined;
        render(tree());
        const button = screen.getByRole('button', { name: 'Download PDF' });
        fireEvent.click(button);
        const busy = await screen.findByRole('button', { name: 'Preparing the PDF…' });
        expect(busy).toBeDisabled();
        expect(busy).toHaveAttribute('aria-busy', 'true');
        fireEvent.click(busy);
        expect(server.calls).toHaveLength(1);
        server.release?.();
        await waitFor(() => expect(server.saved).toHaveLength(1));
        expect(await screen.findByRole('button', { name: 'Download PDF' })).not.toBeDisabled();
    });

    it('says what went wrong, in words, and saves nothing', async () => {
        server.error = { status: 413, data: { code: 'pdf_too_large' } };
        render(tree());
        fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'This response is too long for a PDF.', variant: 'destructive' }));
        expect(server.saved).toHaveLength(0);
        // and it can be tried again
        expect(screen.getByRole('button', { name: 'Download PDF' })).not.toBeDisabled();
    });
});

describe('the refusals', () => {
    it('are told by code first, then by status', () => {
        expect(pdfFailureMessage({ status: 429, data: { code: 'rate_limited', retryAfter: 600 } })).toEqual({ key: 'RESPONSE_PAGE.PDF_ERROR_RATE_LIMITED', values: { minutes: 10 } });
        expect(pdfFailureMessage({ status: 429, data: { code: 'export_busy' } })).toEqual({ key: 'RESPONSE_PAGE.PDF_ERROR_BUSY' });
        expect(pdfFailureMessage({ status: 429 })).toMatchObject({ key: 'RESPONSE_PAGE.PDF_ERROR_RATE_LIMITED', values: { minutes: 1 } });
        expect(pdfFailureMessage({ status: 413 })).toEqual({ key: 'RESPONSE_PAGE.PDF_ERROR_TOO_LARGE' });
        expect(pdfFailureMessage({ status: 403 })).toEqual({ key: 'RESPONSE_PAGE.PDF_ERROR_FORBIDDEN' });
        expect(pdfFailureMessage({ status: 404 })).toEqual({ key: 'RESPONSE_PAGE.PDF_ERROR_MISSING' });
        expect(pdfFailureMessage({ status: 500 })).toEqual({ key: 'RESPONSE_PAGE.PDF_ERROR_GENERIC' });
        expect(pdfFailureMessage(undefined)).toEqual({ key: 'RESPONSE_PAGE.PDF_ERROR_GENERIC' });
    });

    it('all have words in English and in Dutch', () => {
        const keys = ['PDF', 'PDF_PREPARING', 'PDF_DONE', 'PDF_ERROR_RATE_LIMITED', 'PDF_ERROR_TOO_LARGE', 'PDF_ERROR_FORBIDDEN', 'PDF_ERROR_MISSING', 'PDF_ERROR_BUSY', 'PDF_ERROR_GENERIC'];
        for (const key of keys) {
            expect((commonEn as any).RESPONSE_PAGE[key], `en ${key}`).toBeTruthy();
            expect((commonNl as any).RESPONSE_PAGE[key], `nl ${key}`).toBeTruthy();
        }
    });
});

import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { axeViolations } from '@app/test/axe';

import { AuditExportMenu } from './export-menu';

const request = vi.fn();
const save = vi.fn();
vi.mock('@app/store/workspaces/audit-export', () => ({
    requestAuditExport: (...args: unknown[]) => request(...args),
    saveBlob: (...args: unknown[]) => save(...args)
}));

const QUERY = 'area=access&actor=u_sanne';

beforeEach(() => {
    request.mockReset();
    save.mockReset();
    request.mockResolvedValue({ ok: true, fileName: 'audit-log-2026-11-02.csv', blob: new Blob(['x']) });
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

// Radix opens its menu on the key, as the other menus' tests do
const openMenu = async (name: RegExp = /Export/) => {
    fireEvent.keyDown(screen.getByRole('button', { name }), { key: 'Enter' });
    await screen.findAllByRole('menuitem');
};
const choose = (name: string) => fireEvent.click(screen.getByRole('menuitem', { name }));

describe('the export menu', () => {
    it('is a button that opens a menu of the two formats, with a note that exporting is recorded', async () => {
        render(<AuditExportMenu workspaceId="ws1" query={QUERY} />);
        const trigger = screen.getByRole('button', { name: /Export/ });
        expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
        await openMenu();
        expect(screen.getByRole('menuitem', { name: 'CSV file (spreadsheet)' })).toBeInTheDocument();
        expect(screen.getByRole('menuitem', { name: 'JSON file' })).toBeInTheDocument();
        expect(screen.getByText(/Exporting is itself recorded in the log/)).toBeInTheDocument();
    });

    it('asks for the filters on screen in the chosen format and hands the file to the browser', async () => {
        render(<AuditExportMenu workspaceId="ws1" query={QUERY} />);
        await openMenu();
        choose('JSON file');
        await waitFor(() => expect(request).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: undefined, query: QUERY, format: 'json' }));
        await waitFor(() => expect(save).toHaveBeenCalledWith('audit-log-2026-11-02.csv', expect.any(Blob)));
        expect(await screen.findByText('The file audit-log-2026-11-02.csv was downloaded. The export is recorded in the activity log.')).toBeInTheDocument();
    });

    it("asks for a form's own file when it is given a form", async () => {
        render(<AuditExportMenu workspaceId="ws1" formId="f_join" query="" />);
        await openMenu();
        choose('CSV file (spreadsheet)');
        await waitFor(() => expect(request).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f_join', query: '', format: 'csv' }));
    });

    it.each([
        ['too_many_rows', 'That is more than 100,000 entries. Narrow the filters (a date range, a type or a person) and export again.'],
        ['rate_limited', 'Too many exports in a short time. Try again in a few minutes.'],
        ['audit_unavailable', 'The export could not be recorded, so no file was made. Try again in a moment.'],
        ['http_403', 'You do not have access to export this activity.'],
        ['network', 'The file could not be made. Try again.']
    ])('says why when the server refuses (%s) and saves no file', async (code, text) => {
        request.mockResolvedValue({ ok: false, code });
        render(<AuditExportMenu workspaceId="ws1" query={QUERY} />);
        await openMenu();
        choose('CSV file (spreadsheet)');
        expect(await screen.findByRole('alert')).toHaveTextContent(text);
        expect(save).not.toHaveBeenCalled();
    });

    it('is in Dutch too', async () => {
        await i18n.changeLanguage('nl');
        request.mockResolvedValue({ ok: false, code: 'too_many_rows' });
        render(<AuditExportMenu workspaceId="ws1" query={QUERY} />);
        await openMenu(/Exporteren/);
        choose('CSV-bestand (spreadsheet)');
        expect(await screen.findByRole('alert')).toHaveTextContent('Dat zijn meer dan 100.000 regels.');
    });

    it('has no accessibility violations (axe) with the menu open', async () => {
        const { baseElement } = render(<AuditExportMenu workspaceId="ws1" query={QUERY} />);
        await openMenu();
        expect(await axeViolations(baseElement)).toEqual([]);
    });
});

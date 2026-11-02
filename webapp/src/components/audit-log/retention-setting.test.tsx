import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuditRetentionDto } from '@app/models/dtos/audit-log-dto';
import { axeViolations } from '@app/test/axe';

import { AuditRetentionSetting } from './retention-setting';

// ---- the world around the component ---------------------------------------------------------------------------------

const toast = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));

let setting: AuditRetentionDto | undefined;
const save = vi.fn();
let saving = false;
vi.mock('@app/store/workspaces/audit-retention-api', () => ({
    useGetAuditRetentionQuery: () => ({ data: setting }),
    useSetAuditRetentionMutation: () => [save, { isLoading: saving }]
}));

const base: AuditRetentionDto = { months: 12, days: 365, options: [6, 12, 24, 60], minimumMonths: 6, defaultMonths: 12, canChange: true };

beforeEach(() => {
    setting = { ...base };
    saving = false;
    toast.mockReset();
    save.mockReset();
    save.mockResolvedValue({ data: { ...base, months: 24, days: 730 } });
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

const open = () => fireEvent.click(screen.getByRole('button', { name: 'Change retention' }));

describe('the retention setting', () => {
    it('draws nothing for someone who may not change it, or before the server has answered', () => {
        setting = { ...base, canChange: false };
        const { container, rerender } = render(<AuditRetentionSetting workspaceId="ws1" />);
        expect(container).toBeEmptyDOMElement();
        setting = undefined;
        rerender(<AuditRetentionSetting workspaceId="ws1" />);
        expect(container).toBeEmptyDOMElement();
    });

    it('offers exactly the four choices, none under the minimum, with the current one chosen', () => {
        render(<AuditRetentionSetting workspaceId="ws1" />);
        open();
        const dialog = screen.getByRole('dialog');
        const radios = within(dialog).getAllByRole('radio');
        expect(radios.map((r) => (r as HTMLInputElement).closest('label')?.textContent)).toEqual(['6 months', '12 months(default)', '24 months', '60 months']);
        expect(radios.map((r) => (r as HTMLInputElement).checked)).toEqual([false, true, false, false]);
        expect(within(dialog).getByText(/never for less than 6 months/)).toBeInTheDocument();
        // nothing to save until a different period is chosen
        expect(within(dialog).getByRole('button', { name: 'Save' })).toBeDisabled();
    });

    it('never lists a choice under the minimum even if the server sent one', () => {
        setting = { ...base, options: [3, 6, 12, 24, 60] };
        render(<AuditRetentionSetting workspaceId="ws1" />);
        open();
        expect(screen.getAllByRole('radio')).toHaveLength(4);
    });

    it('saves a longer period and says what it comes to', async () => {
        render(<AuditRetentionSetting workspaceId="ws1" />);
        open();
        fireEvent.click(screen.getByRole('radio', { name: /24 months/ }));
        expect(screen.queryByRole('status')).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Save' }));
        await waitFor(() => expect(save).toHaveBeenCalledWith({ workspaceId: 'ws1', months: 24 }));
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Saved. Entries are kept for 24 months.' }));
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('says before it saves that a shorter period deletes at the next daily clean-up, and then says it again', async () => {
        save.mockResolvedValue({ data: { ...base, months: 6, days: 183, appliesAtNextPurge: true } });
        render(<AuditRetentionSetting workspaceId="ws1" />);
        open();
        fireEvent.click(screen.getByRole('radio', { name: /^6 months/ }));
        expect(screen.getByRole('status')).toHaveTextContent('Entries older than 6 months are deleted for good at the next daily clean-up, not at once. They cannot be brought back.');
        fireEvent.click(screen.getByRole('button', { name: 'Shorten retention' }));
        await waitFor(() => expect(save).toHaveBeenCalledWith({ workspaceId: 'ws1', months: 6 }));
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Saved. Entries older than 6 months are deleted at the next daily clean-up.' }));
    });

    it('keeps the dialog open and says so when the change was refused', async () => {
        save.mockResolvedValue({ error: { status: 503, data: { code: 'audit_unavailable' } } });
        render(<AuditRetentionSetting workspaceId="ws1" />);
        open();
        fireEvent.click(screen.getByRole('radio', { name: /60 months/ }));
        fireEvent.click(screen.getByRole('button', { name: 'Save' }));
        expect(await screen.findByRole('alert')).toHaveTextContent('The change could not be recorded, so it was not made. Try again in a moment.');
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(toast).not.toHaveBeenCalled();

        save.mockResolvedValue({ error: { status: 403, data: { code: 'forbidden' } } });
        fireEvent.click(screen.getByRole('button', { name: 'Save' }));
        await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('The setting could not be saved. Try again.'));
    });

    it('cancelling changes nothing and forgets the choice', () => {
        render(<AuditRetentionSetting workspaceId="ws1" />);
        open();
        fireEvent.click(screen.getByRole('radio', { name: /60 months/ }));
        fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
        expect(save).not.toHaveBeenCalled();
        open();
        expect((screen.getByRole('radio', { name: /^12 months/ }) as HTMLInputElement).checked).toBe(true);
    });

    it('is in Dutch too', async () => {
        await i18n.changeLanguage('nl');
        render(<AuditRetentionSetting workspaceId="ws1" />);
        fireEvent.click(screen.getByRole('button', { name: 'Bewaartermijn wijzigen' }));
        const dialog = screen.getByRole('dialog');
        expect(within(dialog).getByText('Regels bewaren gedurende')).toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole('radio', { name: /^6 maanden/ }));
        expect(within(dialog).getByRole('status')).toHaveTextContent('Regels ouder dan 6 maanden worden bij de eerstvolgende dagelijkse opschoning definitief verwijderd, niet meteen.');
        expect(within(dialog).getByRole('button', { name: 'Bewaartermijn verkorten' })).toBeEnabled();
    });

    it('has no accessibility violations (axe) with the dialog open', async () => {
        const { baseElement } = render(<AuditRetentionSetting workspaceId="ws1" />);
        open();
        fireEvent.click(screen.getByRole('radio', { name: /^6 months/ }));
        expect(await axeViolations(baseElement)).toEqual([]);
    });
});

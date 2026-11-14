import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shadcn/components/ui/use-toast';
import '@app/shared/hocs/i18n-provider';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

import SpamCheckSettings, { CaptchaCountsLines } from './spam-check-settings';

const permissions = { can: (_: WorkspacePermission) => true, ready: true, captchaEnabled: true };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => permissions }));
vi.mock('@app/store/hooks', () => ({ useAppSelector: () => ({ id: 'ws-1' }) }));
vi.mock('@app/store/workspaces/slice', () => ({ selectWorkspace: () => ({ id: 'ws-1' }) }));
const toast = vi.hoisted(() => vi.fn());
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));

const save = vi.fn();
const settings = { data: { captchaDefault: true, canManage: true } as any, isLoading: false, isError: false };
const counts = { data: { days: 30, submit: { passed: 12, blocked: 5 }, mail: { passed: 3, blocked: 1 } } as any, isError: false };
vi.mock('@app/store/workspaces/captcha-api', () => ({
    useGetCaptchaSettingsQuery: () => settings,
    useGetWorkspaceCaptchaCountsQuery: () => counts,
    useSetCaptchaDefaultMutation: () => [save, { isLoading: false }]
}));

beforeEach(() => {
    save.mockReset().mockResolvedValue({ data: { captchaDefault: false } });
    toast.mockReset();
    Object.assign(permissions, { can: () => true, ready: true, captchaEnabled: true });
    settings.data = { captchaDefault: true, canManage: true };
});

describe('Spam protection settings', () => {
    it('shows the default as a labelled switch, on unless the workspace chose otherwise, and saves a change at once', async () => {
        render(<SpamCheckSettings />);
        const toggle = screen.getByRole('switch', { name: /spam protection on forms by default/i });
        expect(toggle.getAttribute('aria-checked')).toBe('true');
        expect(toggle.getAttribute('aria-describedby')).toBe('spam-default-description');
        fireEvent.click(toggle);
        await waitFor(() => expect(save).toHaveBeenCalledWith({ workspaceId: 'ws-1', captchaDefault: false }));
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Spam protection is off by default.' }));
    });

    it('says so when the change could not be saved', async () => {
        save.mockResolvedValue({ error: { status: 503 } });
        render(<SpamCheckSettings />);
        fireEvent.click(screen.getByRole('switch'));
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'The setting could not be saved. Try again.', variant: 'destructive' }));
    });

    it('shows counts only, with the note that nothing about a visitor is kept', () => {
        render(<SpamCheckSettings />);
        const lines = screen.getByTestId('spam-counts').textContent ?? '';
        expect(lines).toContain('Form submits, last 30 days: 12 passed, 5 blocked');
        expect(lines).toContain('Sign-in code and draft link mails, last 30 days: 3 passed, 1 blocked');
        expect(screen.getByText(/Nothing about a visitor, an address or a network is kept/)).toBeTruthy();
    });

    it('is for managers of the workspace, and only while the server has the check on', () => {
        permissions.can = () => false;
        const { unmount } = render(<SpamCheckSettings />);
        expect(screen.getByText(/Only workspace owners and admins/)).toBeTruthy();
        expect(screen.queryByRole('switch')).toBeNull();
        unmount();
        permissions.can = () => true;
        permissions.captchaEnabled = false;
        render(<SpamCheckSettings />);
        expect(screen.getByText(/not switched on on this server/)).toBeTruthy();
        expect(screen.queryByRole('switch')).toBeNull();
    });

    it('lets a member who may not manage see the switch off', () => {
        settings.data = { captchaDefault: false, canManage: false };
        render(<SpamCheckSettings />);
        const toggle = screen.getByRole('switch') as HTMLButtonElement;
        expect(toggle.getAttribute('aria-checked')).toBe('false');
        expect(toggle.disabled).toBe(true);
    });

    it('words the counts in Dutch too', () => {
        // the strings exist in both languages, with the same placeholders
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const en = require('../../../public/locales/en/common.json').STAFF.SPAM_CHECK;
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const nl = require('../../../public/locales/nl/common.json').STAFF.SPAM_CHECK;
        expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
        for (const key of ['COUNTS_SUBMIT', 'COUNTS_MAIL']) {
            for (const placeholder of ['{{days}}', '{{passed}}', '{{blocked}}']) expect(nl[key]).toContain(placeholder);
        }
    });

    it('renders nothing for counts that have not arrived', () => {
        const { container } = render(<CaptchaCountsLines />);
        expect(container.firstChild).toBeNull();
    });
});

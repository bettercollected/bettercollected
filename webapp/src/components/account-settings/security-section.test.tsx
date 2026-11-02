import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shadcn/components/ui/use-toast';
import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import SecuritySection from './security-section';

const statusQuery: { data: any } = { data: undefined };
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetMfaStatusQuery: () => statusQuery,
        useLogoutMutation: () => [vi.fn()],
        useStartTotpEnrolmentMutation: () => [vi.fn().mockResolvedValue({ data: { factorId: 'f1', secret: 'AAAA BBBB', uri: 'otpauth://totp/x?secret=AAAABBBB' } }), { reset: vi.fn() }],
        useConfirmTotpEnrolmentMutation: () => [vi.fn(), { isLoading: false, reset: vi.fn() }],
        useDisableTotpMutation: () => [vi.fn(), { isLoading: false, reset: vi.fn() }],
        useRegenerateRecoveryCodesMutation: () => [vi.fn(), { isLoading: false, reset: vi.fn() }]
    };
});

describe('SecuritySection (the authenticator app, in account settings)', () => {
    beforeEach(() => {
        statusQuery.data = undefined;
    });

    it('is absent until the answer arrives, and while the server has the switch off', () => {
        const { container, rerender } = render(<SecuritySection />);
        expect(container).toBeEmptyDOMElement();
        statusQuery.data = { available: false, enabled: false };
        rerender(<SecuritySection />);
        expect(container).toBeEmptyDOMElement();
    });

    it('offers to set it up when it is off, and opens the setup', async () => {
        statusQuery.data = { available: true, enabled: false };
        render(<SecuritySection />);
        expect(screen.getByTestId('totp-state').textContent).toBe('Not set up.');
        expect(screen.queryByRole('button', { name: 'Turn off' })).toBeNull();
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Set up an authenticator app' }));
        expect(await screen.findByText('Scan the QR code')).toBeInTheDocument();
    });

    it('says it is on, with the recovery codes left, and offers new codes and turning it off', async () => {
        statusQuery.data = { available: true, enabled: true, recoveryLeft: 7 };
        render(<SecuritySection />);
        expect(screen.getByTestId('totp-state').textContent).toBe('On. 7 recovery codes left.');
        expect(screen.queryByRole('status')).toBeNull();
        expect(screen.queryByRole('button', { name: 'Set up an authenticator app' })).toBeNull();
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Turn off' }));
        expect(await screen.findByRole('dialog', { name: 'Turn off the authenticator app' })).toBeInTheDocument();
    });

    it('warns when only a few recovery codes are left', () => {
        statusQuery.data = { available: true, enabled: true, recoveryLeft: 1 };
        render(<SecuritySection />);
        expect(screen.getByTestId('totp-state').textContent).toBe('On. 1 recovery code left.');
        expect(screen.getByRole('status').textContent).toMatch(/Only 1 recovery code left/);
    });

    it('warns when none are left', () => {
        statusQuery.data = { available: true, enabled: true, recoveryLeft: 0 };
        render(<SecuritySection />);
        expect(screen.getByRole('status').textContent).toMatch(/No recovery codes left/);
    });
});

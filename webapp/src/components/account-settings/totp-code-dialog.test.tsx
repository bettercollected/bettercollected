import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import TotpCodeDialog from './totp-code-dialog';

const disableMock = vi.fn();
const regenerateMock = vi.fn();
const resetMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useDisableTotpMutation: () => [disableMock, { isLoading: false, reset: resetMock }],
        useRegenerateRecoveryCodesMutation: () => [regenerateMock, { isLoading: false, reset: resetMock }]
    };
});

describe('TotpCodeDialog (changes that need a fresh code)', () => {
    beforeEach(() => {
        disableMock.mockReset().mockResolvedValue({ data: { available: true, enabled: false } });
        regenerateMock.mockReset().mockResolvedValue({ data: { recoveryCodes: ['AAAA-BBBB-CCCC-DDDD'] } });
        resetMock.mockReset();
    });

    it('turns the factor off with a code from the app', async () => {
        const onDisabled = vi.fn();
        render(<TotpCodeDialog action="disable" onClose={vi.fn()} onDisabled={onDisabled} />);
        const input = screen.getByLabelText('6-digit code') as HTMLInputElement;
        expect(input.getAttribute('autocomplete')).toBe('one-time-code');
        expect(input.getAttribute('inputmode')).toBe('numeric');
        expect(screen.getByRole('button', { name: 'Turn off' })).toBeDisabled();
        fireEvent.change(input, { target: { value: '123 456' } });
        fireEvent.click(screen.getByRole('button', { name: 'Turn off' }));
        await waitFor(() => expect(onDisabled).toHaveBeenCalled());
        expect(disableMock).toHaveBeenCalledWith({ code: '123456' });
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('accepts a recovery code in its own field', async () => {
        render(<TotpCodeDialog action="disable" onClose={vi.fn()} onDisabled={vi.fn()} />);
        fireEvent.click(screen.getByRole('button', { name: 'Use a recovery code' }));
        const input = screen.getByLabelText('Recovery code') as HTMLInputElement;
        expect(input.getAttribute('autocomplete')).toBe('off');
        fireEvent.change(input, { target: { value: 'abcd-efgh-ijkl-mnop' } });
        fireEvent.click(screen.getByRole('button', { name: 'Turn off' }));
        await waitFor(() => expect(disableMock).toHaveBeenCalledWith({ code: 'ABCD-EFGH-IJKL-MNOP' }));
        expect(screen.getByRole('button', { name: 'Use the code from my app' })).toBeInTheDocument();
    });

    it('keeps the dialog open and says so when the code is wrong', async () => {
        disableMock.mockResolvedValue({ error: { status: 422, data: { code: 'invalid_code' } } });
        const onDisabled = vi.fn();
        render(<TotpCodeDialog action="disable" onClose={vi.fn()} onDisabled={onDisabled} />);
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '000000' } });
        fireEvent.click(screen.getByRole('button', { name: 'Turn off' }));
        expect(await screen.findByText('That code is not valid. Enter the code your app shows now.')).toBeInTheDocument();
        expect(onDisabled).not.toHaveBeenCalled();
    });

    it('shows a lock with its time', async () => {
        disableMock.mockResolvedValue({ error: { status: 429, data: { code: 'mfa_locked', retry_after: 899 } } });
        render(<TotpCodeDialog action="disable" onClose={vi.fn()} onDisabled={vi.fn()} />);
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '000000' } });
        fireEvent.click(screen.getByRole('button', { name: 'Turn off' }));
        expect(await screen.findByText('Too many attempts. Try again in 15 minutes.')).toBeInTheDocument();
    });

    it('makes new recovery codes with a fresh code and shows them once', async () => {
        const onClose = vi.fn();
        render(<TotpCodeDialog action="regenerate" onClose={onClose} onDisabled={vi.fn()} />);
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
        fireEvent.click(screen.getByRole('button', { name: 'Make new codes' }));
        expect(await screen.findByText('AAAA-BBBB-CCCC-DDDD')).toBeInTheDocument();
        expect(regenerateMock).toHaveBeenCalledWith({ code: '123456' });
        expect(screen.getByRole('button', { name: 'Done' })).toBeDisabled();
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(screen.getByLabelText('I have stored these codes in a safe place.'));
        fireEvent.click(screen.getByRole('button', { name: 'Done' }));
        expect(onClose).toHaveBeenCalled();
    });
});

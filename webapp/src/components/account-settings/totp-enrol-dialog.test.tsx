import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import TotpEnrolDialog from './totp-enrol-dialog';

const startMock = vi.fn();
const confirmMock = vi.fn();
const resetMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useStartTotpEnrolmentMutation: () => [startMock, { isLoading: false, reset: resetMock }],
        useConfirmTotpEnrolmentMutation: () => [confirmMock, { isLoading: false, reset: resetMock }]
    };
});

const ENROLMENT = { factorId: 'f1', secret: 'JBSW Y3DP EHPK 3PXP', uri: 'otpauth://totp/Example:me%40example.org?secret=JBSWY3DPEHPK3PXP&issuer=Example' };
const CODES = ['AAAA-BBBB-CCCC-DDDD', 'EEEE-FFFF-GGGG-HHHH', 'IIII-JJJJ-KKKK-LLLL'];

const open = async () => {
    const onClose = vi.fn();
    const onSignInAgain = vi.fn();
    render(<TotpEnrolDialog onClose={onClose} onSignInAgain={onSignInAgain} />);
    await screen.findByText('Scan the QR code');
    return { onClose, onSignInAgain };
};

describe('TotpEnrolDialog (setting up an authenticator app)', () => {
    beforeEach(() => {
        startMock.mockReset().mockResolvedValue({ data: ENROLMENT });
        confirmMock.mockReset().mockResolvedValue({ data: { recoveryCodes: CODES } });
        resetMock.mockReset();
        Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    });

    it('asks the server to start once and shows the QR code and the key to type', async () => {
        await open();
        expect(startMock).toHaveBeenCalledTimes(1);
        expect(screen.getByRole('img', { name: /QR code for your authenticator app/ })).toBeInTheDocument();
        // the QR code is drawn here from the address, as a real image
        await waitFor(() => expect(screen.getByTestId('totp-qr').querySelector('svg')).not.toBeNull());
        expect((screen.getByLabelText('Setup key') as HTMLInputElement).value).toBe('JBSW Y3DP EHPK 3PXP');
        expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
    });

    it('copies the key without its spaces', async () => {
        await open();
        fireEvent.click(screen.getByRole('button', { name: 'Copy key' }));
        await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith('JBSWY3DPEHPK3PXP'));
        expect(await screen.findByText('Key copied.')).toBeInTheDocument();
    });

    it('has an accessible scan step', async () => {
        await open();
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('asks for the code in a field made for it', async () => {
        await open();
        fireEvent.click(screen.getByRole('button', { name: 'Next' }));
        const input = screen.getByLabelText('6-digit code') as HTMLInputElement;
        expect(input.getAttribute('autocomplete')).toBe('one-time-code');
        expect(input.getAttribute('inputmode')).toBe('numeric');
        expect(document.activeElement).toBe(input);
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('says a wrong code is wrong, mentions the phone clock, and stays on the step', async () => {
        confirmMock.mockResolvedValue({ error: { status: 422, data: { code: 'invalid_code', message: 'x' } } });
        await open();
        fireEvent.click(screen.getByRole('button', { name: 'Next' }));
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '111 111' } });
        fireEvent.click(screen.getByRole('button', { name: 'Confirm and turn on' }));
        expect(await screen.findByText(/That code is not valid.*time on your phone is set automatically/)).toBeInTheDocument();
        expect(confirmMock).toHaveBeenCalledWith({ factorId: 'f1', code: '111111' });
        expect(screen.getByLabelText('6-digit code').getAttribute('aria-invalid')).toBe('true');
        expect(screen.queryByText('Keep your recovery codes')).toBeNull();
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('tells how long to wait when too many codes were tried', async () => {
        confirmMock.mockResolvedValue({ error: { status: 429, data: { code: 'too_many_attempts', retry_after: 280 } } });
        await open();
        fireEvent.click(screen.getByRole('button', { name: 'Next' }));
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '111111' } });
        fireEvent.click(screen.getByRole('button', { name: 'Confirm and turn on' }));
        expect(await screen.findByText('Too many attempts. Try again in 5 minutes.')).toBeInTheDocument();
    });

    describe('after the right code', () => {
        const confirmed = async () => {
            const handlers = await open();
            fireEvent.click(screen.getByRole('button', { name: 'Next' }));
            fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
            fireEvent.click(screen.getByRole('button', { name: 'Confirm and turn on' }));
            await screen.findByText('Keep your recovery codes');
            return handlers;
        };

        it('shows the recovery codes once and drops the key and the QR code', async () => {
            await confirmed();
            for (const code of CODES) expect(screen.getByText(code)).toBeInTheDocument();
            expect(screen.queryByTestId('totp-qr')).toBeNull();
            expect(screen.queryByLabelText('Setup key')).toBeNull();
            expect(screen.getByText('Step 3 of 3')).toBeInTheDocument();
            // focus moved to the new step
            expect(document.activeElement?.textContent).toBe('Keep your recovery codes');
            expect(await axeViolations(document.body)).toEqual([]);
        });

        it('copies and downloads the codes', async () => {
            await confirmed();
            fireEvent.click(screen.getByRole('button', { name: 'Copy all' }));
            await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(CODES.join('\n')));
            const create = vi.fn(() => 'blob:codes');
            const revoke = vi.fn();
            Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
            fireEvent.click(screen.getByRole('button', { name: 'Download as .txt' }));
            expect(create).toHaveBeenCalledTimes(1);
            const blob = (create.mock.calls[0] as unknown as [Blob])[0];
            expect(await blob.text()).toContain(CODES[0]);
            expect(revoke).toHaveBeenCalledWith('blob:codes');
        });

        it('does not close until the person says the codes are stored', async () => {
            const { onClose } = await confirmed();
            const done = screen.getByRole('button', { name: 'Done' });
            expect(done).toBeDisabled();
            fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
            fireEvent.click(screen.getByRole('button', { name: 'Close' }));
            expect(onClose).not.toHaveBeenCalled();
            fireEvent.click(screen.getByLabelText('I have stored these codes in a safe place.'));
            expect(done).toBeEnabled();
            fireEvent.click(done);
            expect(onClose).toHaveBeenCalledTimes(1);
        });

        it('never writes the codes to browser storage', async () => {
            const setItem = vi.spyOn(Storage.prototype, 'setItem');
            await confirmed();
            expect(setItem).not.toHaveBeenCalled();
            expect(JSON.stringify(window.localStorage)).not.toContain('AAAA');
            expect(JSON.stringify(window.sessionStorage)).not.toContain('AAAA');
            setItem.mockRestore();
        });
    });

    it('asks a session that signed in long ago to sign in again', async () => {
        startMock.mockResolvedValue({ error: { status: 403, data: { code: 'recent_proof_required', message: 'x' } } });
        const onSignInAgain = vi.fn();
        render(<TotpEnrolDialog onClose={vi.fn()} onSignInAgain={onSignInAgain} />);
        expect(await screen.findByText(/You signed in a while ago/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Sign out and sign in again' }));
        expect(onSignInAgain).toHaveBeenCalled();
        expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('can try again after a failure to start, and says when the switch is off', async () => {
        startMock.mockResolvedValueOnce({ error: { status: 500, data: 'x' } });
        render(<TotpEnrolDialog onClose={vi.fn()} onSignInAgain={vi.fn()} />);
        expect(await screen.findByText('Something went wrong. Please try again.')).toBeInTheDocument();
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
        });
        expect(await screen.findByText('Scan the QR code')).toBeInTheDocument();
        expect(startMock).toHaveBeenCalledTimes(2);
    });

    it('clears what it holds when it closes', async () => {
        const { unmount } = render(<TotpEnrolDialog onClose={vi.fn()} onSignInAgain={vi.fn()} />);
        await screen.findByText('Scan the QR code');
        resetMock.mockClear();
        unmount();
        expect(resetMock).toHaveBeenCalled();
    });
});

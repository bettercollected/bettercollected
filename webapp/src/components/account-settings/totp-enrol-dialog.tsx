'use client';

import React, { useEffect, useRef, useState } from 'react';

import { useQRCode } from 'next-qrcode';

import { useTranslation } from 'react-i18next';

import CodeEntry from '@app/components/mfa/code-entry';
import { mfaErrorText } from '@app/components/mfa/error-text';
import RecoveryCodes from '@app/components/mfa/recovery-codes';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { useConfirmTotpEnrolmentMutation, useStartTotpEnrolmentMutation } from '@app/store/auth/api';
import { TotpEnrolment } from '@app/store/auth/types';
import { MfaFailure, mfaFailureOf, normaliseCode } from '@app/utils/mfa';

type Step = 'loading' | 'scan' | 'code' | 'codes' | 'failed';

/**
 * Setting up an authenticator app, in three steps: scan the QR code (or type
 * the key), enter the first code, keep the recovery codes. The QR code is drawn
 * here from the address the server gave once; the key and the codes live in
 * this component's state only and are dropped as soon as it closes (nothing
 * goes to storage, the store or a log). Closing before the codes are kept is
 * not possible: they are shown once.
 */
export default function TotpEnrolDialog({ onClose, onSignInAgain, onEnrolled }: { onClose: () => void; onSignInAgain: () => void; onEnrolled?: () => void }) {
    const { t } = useTranslation();
    const { SVG } = useQRCode();
    const [start, startState] = useStartTotpEnrolmentMutation();
    const [confirm, confirmState] = useConfirmTotpEnrolmentMutation();
    const [step, setStep] = useState<Step>('loading');
    const [enrolment, setEnrolment] = useState<TotpEnrolment | null>(null);
    const [failure, setFailure] = useState<MfaFailure>({});
    const [code, setCode] = useState('');
    const [codeError, setCodeError] = useState('');
    const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
    const [acknowledged, setAcknowledged] = useState(false);
    const [keyCopied, setKeyCopied] = useState<'yes' | 'no' | ''>('');
    const heading = useRef<HTMLHeadingElement>(null);
    const requested = useRef(false);
    const { reset: resetStart } = startState;
    const { reset: resetConfirm } = confirmState;

    const begin = async () => {
        setStep('loading');
        const answer = await start();
        if ('data' in answer && answer.data) {
            setEnrolment(answer.data);
            setStep('scan');
        } else {
            setFailure(mfaFailureOf((answer as { error?: unknown }).error));
            setStep('failed');
        }
    };

    useEffect(() => {
        if (requested.current) return;
        requested.current = true;
        void begin();
        // once per opening
    }, []);

    // the secret and the codes leave memory with the dialog
    useEffect(
        () => () => {
            resetStart();
            resetConfirm();
        },
        [resetStart, resetConfirm]
    );

    // a new step starts at its heading, for screen-reader and keyboard users
    useEffect(() => {
        if (step === 'scan' || step === 'codes' || step === 'failed') heading.current?.focus();
    }, [step]);

    const copyKey = async () => {
        if (!enrolment) return;
        try {
            await navigator.clipboard.writeText(enrolment.secret.replace(/\s+/g, ''));
            setKeyCopied('yes');
        } catch {
            setKeyCopied('no');
        }
    };

    const submitCode = async (event: React.FormEvent) => {
        event.preventDefault();
        const typed = normaliseCode(code, false);
        if (!enrolment || !typed) return;
        setCodeError('');
        const answer = await confirm({ factorId: enrolment.factorId, code: typed });
        if ('data' in answer && answer.data) {
            // the key is no longer needed: drop it with the QR code
            setRecoveryCodes(answer.data.recoveryCodes);
            setEnrolment(null);
            setCode('');
            setStep('codes');
            return;
        }
        const refused = mfaFailureOf((answer as { error?: unknown }).error);
        if (refused.code === 'recent_proof_required' || refused.code === 'totp_off') {
            setFailure(refused);
            setStep('failed');
            return;
        }
        setCodeError(mfaErrorText(t, refused, true));
    };

    const requestClose = () => {
        // the recovery codes are shown once: not closed before they are kept
        if (step === 'codes' && !acknowledged) return;
        onClose();
    };

    const stepNumber = step === 'code' ? 2 : step === 'codes' ? 3 : 1;

    return (
        <Dialog open onOpenChange={(open) => !open && requestClose()}>
            <DialogContent
                className="max-h-[92vh] max-w-lg overflow-y-auto"
                title={t('STAFF.MFA.SETUP.TITLE')}
                onClickCloseIcon={requestClose}
                onEscapeKeyDown={(event) => {
                    if (step === 'codes' && !acknowledged) event.preventDefault();
                }}
                onInteractOutside={(event) => event.preventDefault()}
            >
                <div className="flex flex-col gap-4 pr-6">
                    {step !== 'failed' && step !== 'loading' && <p className="text-xs font-medium tracking-wide text-black-700 uppercase">{t('STAFF.MFA.SETUP.STEP', { step: stepNumber, total: 3 })}</p>}

                    {step === 'loading' && <p className="text-sm text-black-700">{t('STAFF.MFA.SETUP.PREPARING')}</p>}

                    {step === 'failed' && (
                        <>
                            <h2 ref={heading} tabIndex={-1} className="text-lg font-semibold text-black-900 outline-hidden">
                                {t('STAFF.MFA.SETUP.FAILED_TITLE')}
                            </h2>
                            <p role="alert" className="text-sm leading-relaxed text-black-800">
                                {mfaErrorText(t, failure)}
                            </p>
                            <div className="flex flex-wrap justify-end gap-2">
                                <Button type="button" variant="v2Button" size="sm" onClick={onClose}>
                                    {t('STAFF.MFA.CLOSE')}
                                </Button>
                                {failure.code === 'recent_proof_required' ? (
                                    <Button type="button" size="sm" onClick={onSignInAgain}>
                                        {t('STAFF.MFA.SIGN_IN_AGAIN')}
                                    </Button>
                                ) : failure.code === 'totp_off' ? null : (
                                    <Button type="button" size="sm" onClick={() => void begin()}>
                                        {t('STAFF.MFA.TRY_AGAIN')}
                                    </Button>
                                )}
                            </div>
                        </>
                    )}

                    {step === 'scan' && enrolment && (
                        <>
                            <h2 ref={heading} tabIndex={-1} className="text-lg font-semibold text-black-900 outline-hidden">
                                {t('STAFF.MFA.SETUP.SCAN_TITLE')}
                            </h2>
                            <p className="text-sm leading-relaxed text-black-800">{t('STAFF.MFA.SETUP.SCAN_INTRO')}</p>
                            <div className="flex justify-center">
                                <div role="img" aria-label={t('STAFF.MFA.SETUP.QR_LABEL')} data-testid="totp-qr" className="h-[208px] w-[208px] overflow-hidden rounded border border-black-300 bg-white [&_svg]:block [&_svg]:h-full [&_svg]:w-full">
                                    <SVG text={enrolment.uri} options={{ type: 'svg', margin: 2, width: 208, errorCorrectionLevel: 'M', color: { dark: '#000000', light: '#FFFFFF' } }} />
                                </div>
                            </div>
                            <div className="flex flex-col gap-1.5">
                                <label htmlFor="totp-manual-key" className="text-sm font-medium text-black-900">
                                    {t('STAFF.MFA.SETUP.MANUAL_LABEL')}
                                </label>
                                <p className="text-xs leading-relaxed text-black-700">{t('STAFF.MFA.SETUP.MANUAL_HINT')}</p>
                                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                                    <input
                                        id="totp-manual-key"
                                        readOnly
                                        value={enrolment.secret}
                                        spellCheck={false}
                                        autoComplete="off"
                                        onFocus={(event) => event.currentTarget.select()}
                                        className="h-10 w-full rounded-md border border-control bg-white px-3.5 font-mono text-sm tracking-wider text-black-900 sm:flex-1"
                                    />
                                    <Button type="button" variant="v2Button" size="sm" onClick={copyKey}>
                                        {t('STAFF.MFA.SETUP.COPY_KEY')}
                                    </Button>
                                </div>
                                <p role="status" className="min-h-4 text-xs text-black-700">
                                    {keyCopied === 'yes' ? t('STAFF.MFA.SETUP.KEY_COPIED') : keyCopied === 'no' ? t('STAFF.MFA.SETUP.COPY_FAILED') : ''}
                                </p>
                            </div>
                            <div className="flex justify-end gap-2">
                                <Button type="button" variant="v2Button" size="sm" onClick={onClose}>
                                    {t('STAFF.MFA.CANCEL')}
                                </Button>
                                <Button type="button" size="sm" onClick={() => setStep('code')}>
                                    {t('STAFF.MFA.NEXT')}
                                </Button>
                            </div>
                        </>
                    )}

                    {step === 'code' && (
                        <form onSubmit={submitCode} className="flex flex-col gap-4" noValidate>
                            <h2 className="text-lg font-semibold text-black-900">{t('STAFF.MFA.SETUP.CODE_TITLE')}</h2>
                            <p className="text-sm leading-relaxed text-black-800">{t('STAFF.MFA.SETUP.CODE_INTRO')}</p>
                            <CodeEntry
                                id="totp-setup-code"
                                value={code}
                                onChange={(value) => {
                                    setCode(value);
                                    setCodeError('');
                                }}
                                error={codeError}
                                autoFocus
                                disabled={confirmState.isLoading}
                            />
                            <div className="flex justify-end gap-2">
                                <Button type="button" variant="v2Button" size="sm" onClick={() => setStep('scan')}>
                                    {t('STAFF.MFA.BACK')}
                                </Button>
                                <Button type="submit" size="sm" isLoading={confirmState.isLoading} disabled={!code.trim()}>
                                    {t('STAFF.MFA.SETUP.CONFIRM')}
                                </Button>
                            </div>
                        </form>
                    )}

                    {step === 'codes' && (
                        <>
                            <h2 ref={heading} tabIndex={-1} className="text-lg font-semibold text-black-900 outline-hidden">
                                {t('STAFF.MFA.SETUP.CODES_TITLE')}
                            </h2>
                            <RecoveryCodes codes={recoveryCodes} acknowledged={acknowledged} onAcknowledge={setAcknowledged} />
                            <div className="flex justify-end">
                                <Button
                                    type="button"
                                    size="sm"
                                    disabled={!acknowledged}
                                    onClick={() => {
                                        onClose();
                                        onEnrolled?.();
                                    }}
                                >
                                    {t('STAFF.MFA.DONE')}
                                </Button>
                            </div>
                        </>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

'use client';

import React, { useEffect, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import CodeEntry from '@app/components/mfa/code-entry';
import { mfaErrorText } from '@app/components/mfa/error-text';
import RecoveryCodes from '@app/components/mfa/recovery-codes';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { useDisableTotpMutation, useRegenerateRecoveryCodesMutation } from '@app/store/auth/api';
import { mfaFailureOf, normaliseCode } from '@app/utils/mfa';

export type TotpCodeAction = 'disable' | 'regenerate';

/**
 * A change that needs a fresh code in the same request: turning the factor off
 * or making new recovery codes (which end the old ones). A recovery code works
 * here too, for someone who lost the phone. The new recovery codes are shown
 * once, in this dialog, and dropped when it closes.
 */
export default function TotpCodeDialog({ action, onClose, onDisabled }: { action: TotpCodeAction; onClose: () => void; onDisabled: () => void }) {
    const { t } = useTranslation();
    const [disable, disableState] = useDisableTotpMutation();
    const [regenerate, regenerateState] = useRegenerateRecoveryCodesMutation();
    const [code, setCode] = useState('');
    const [recovery, setRecovery] = useState(false);
    const [error, setError] = useState('');
    const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
    const [acknowledged, setAcknowledged] = useState(false);
    const heading = useRef<HTMLHeadingElement>(null);
    const { reset: resetDisable } = disableState;
    const { reset: resetRegenerate } = regenerateState;
    const busy = disableState.isLoading || regenerateState.isLoading;
    const key = action === 'disable' ? 'DISABLE' : 'REGENERATE';

    useEffect(
        () => () => {
            resetDisable();
            resetRegenerate();
        },
        [resetDisable, resetRegenerate]
    );

    useEffect(() => {
        if (recoveryCodes) heading.current?.focus();
    }, [recoveryCodes]);

    const submit = async (event: React.FormEvent) => {
        event.preventDefault();
        const typed = normaliseCode(code, recovery);
        if (!typed) return;
        setError('');
        if (action === 'disable') {
            const answer = await disable({ code: typed });
            if ('data' in answer && answer.data) {
                onDisabled();
                return;
            }
            setError(mfaErrorText(t, mfaFailureOf((answer as { error?: unknown }).error)));
        } else {
            const answer = await regenerate({ code: typed });
            if ('data' in answer && answer.data) {
                setRecoveryCodes(answer.data.recoveryCodes);
                setCode('');
                return;
            }
            setError(mfaErrorText(t, mfaFailureOf((answer as { error?: unknown }).error)));
        }
    };

    const requestClose = () => {
        if (recoveryCodes && !acknowledged) return;
        onClose();
    };

    return (
        <Dialog open onOpenChange={(open) => !open && requestClose()}>
            <DialogContent
                className="max-h-[92vh] max-w-lg overflow-y-auto"
                title={t(`STAFF.MFA.${key}.TITLE`)}
                onClickCloseIcon={requestClose}
                onEscapeKeyDown={(event) => {
                    if (recoveryCodes && !acknowledged) event.preventDefault();
                }}
                onInteractOutside={(event) => event.preventDefault()}
            >
                {recoveryCodes ? (
                    <div className="flex flex-col gap-4 pr-6">
                        <h2 ref={heading} tabIndex={-1} className="text-lg font-semibold text-black-900 outline-hidden">
                            {t('STAFF.MFA.REGENERATE.NEW_TITLE')}
                        </h2>
                        <RecoveryCodes codes={recoveryCodes} acknowledged={acknowledged} onAcknowledge={setAcknowledged} />
                        <div className="flex justify-end">
                            <Button type="button" size="sm" disabled={!acknowledged} onClick={onClose}>
                                {t('STAFF.MFA.DONE')}
                            </Button>
                        </div>
                    </div>
                ) : (
                    <form onSubmit={submit} className="flex flex-col gap-4 pr-6" noValidate>
                        {/* the dialog's own (visually hidden) title names it for assistive technology */}
                        <div aria-hidden="true" className="text-lg font-semibold text-black-900">
                            {t(`STAFF.MFA.${key}.TITLE`)}
                        </div>
                        <p className="text-sm leading-relaxed text-black-800">{t(`STAFF.MFA.${key}.INTRO`)}</p>
                        <CodeEntry
                            key={recovery ? 'recovery' : 'digits'}
                            id="totp-fresh-code"
                            value={code}
                            recovery={recovery}
                            onChange={(value) => {
                                setCode(value);
                                setError('');
                            }}
                            error={error}
                            autoFocus
                            disabled={busy}
                        />
                        <button
                            type="button"
                            className="w-fit text-sm font-medium text-brand-600 underline underline-offset-2 hover:text-brand-700"
                            onClick={() => {
                                setRecovery(!recovery);
                                setCode('');
                                setError('');
                            }}
                        >
                            {t(recovery ? 'STAFF.MFA.CODE.USE_APP' : 'STAFF.MFA.CODE.USE_RECOVERY')}
                        </button>
                        <div className="flex justify-end gap-2">
                            <Button type="button" variant="v2Button" size="sm" onClick={onClose}>
                                {t('STAFF.MFA.CANCEL')}
                            </Button>
                            <Button type="submit" size="sm" variant={action === 'disable' ? 'danger' : 'primary'} isLoading={busy} disabled={!code.trim()}>
                                {t(`STAFF.MFA.${key}.SUBMIT`)}
                            </Button>
                        </div>
                    </form>
                )}
            </DialogContent>
        </Dialog>
    );
}

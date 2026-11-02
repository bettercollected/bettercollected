'use client';

import React, { useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useGetMfaStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { navigateTo } from '@app/utils/browser-navigation';

import TotpCodeDialog, { TotpCodeAction } from './totp-code-dialog';
import TotpEnrolDialog from './totp-enrol-dialog';

/** At this many recovery codes or fewer the card asks the user to make new ones. */
export const LOW_RECOVERY_CODES = 2;

/**
 * The account's second factor (an authenticator app): whether it is on, how
 * many recovery codes are left, and the ways to set it up, renew the recovery
 * codes and turn it off. The whole card is absent while the server's
 * `TOTP_ENABLED` switch is off (`available` in `GET /auth/mfa/status`), and
 * while that answer has not arrived.
 */
export default function SecuritySection() {
    const { t } = useTranslation();
    const { toast } = useToast();
    const { data: status } = useGetMfaStatusQuery();
    const [logout] = useLogoutMutation();
    const [enrolling, setEnrolling] = useState(false);
    const [changing, setChanging] = useState<TotpCodeAction | null>(null);
    const title = useRef<HTMLHeadingElement>(null);

    // the button that opened a dialog may be gone when it closes (set up becomes turn off): focus returns to the card
    const closed = () => {
        setEnrolling(false);
        setChanging(null);
        requestAnimationFrame(() => title.current?.focus());
    };

    if (!status?.available) return null;

    const left = status.recoveryLeft ?? 0;

    // A session older than a quarter of an hour must sign in again before it may add a factor.
    const signInAgain = async () => {
        await logout();
        const here = `${window.location.pathname}${window.location.search}`;
        navigateTo(`/login?redirect_to=${encodeURIComponent(here)}`);
    };

    return (
        <section aria-labelledby="security-title" className="flex max-w-[640px] flex-col gap-4 rounded border border-black-300 bg-white p-6">
            <div className="flex flex-col gap-1">
                <h2 id="security-title" ref={title} tabIndex={-1} className="text-sm font-semibold text-black-900 outline-hidden">
                    {t('STAFF.MFA.CARD.TITLE')}
                </h2>
                <p className="text-xs leading-relaxed text-black-600">{t('STAFF.MFA.CARD.INTRO')}</p>
            </div>

            <div className="flex flex-col gap-3 rounded-md border border-black-300 px-3 py-3">
                <div className="flex flex-col gap-0.5">
                    <p className="text-[13px] font-medium text-black-800">{t('STAFF.MFA.CARD.APP')}</p>
                    <p data-testid="totp-state" className="text-xs leading-relaxed text-black-700">
                        {status.enabled ? t('STAFF.MFA.CARD.ON', { count: left }) : t('STAFF.MFA.CARD.OFF')}
                    </p>
                    {status.enabled && left <= LOW_RECOVERY_CODES && (
                        <p role="status" className="text-xs leading-relaxed font-medium text-[#B42318]">
                            {t(left === 0 ? 'STAFF.MFA.CARD.NONE_LEFT' : 'STAFF.MFA.CARD.LOW', { count: left })}
                        </p>
                    )}
                </div>
                <div className="flex flex-wrap gap-2">
                    {status.enabled ? (
                        <>
                            <Button type="button" variant="v2Button" size="sm" onClick={() => setChanging('regenerate')}>
                                {t('STAFF.MFA.CARD.REGENERATE')}
                            </Button>
                            <Button type="button" variant="dangerGhost" size="sm" onClick={() => setChanging('disable')}>
                                {t('STAFF.MFA.CARD.TURN_OFF')}
                            </Button>
                        </>
                    ) : (
                        <Button type="button" size="sm" onClick={() => setEnrolling(true)}>
                            {t('STAFF.MFA.CARD.SET_UP')}
                        </Button>
                    )}
                </div>
            </div>

            {enrolling && <TotpEnrolDialog onClose={closed} onSignInAgain={signInAgain} />}
            {changing && (
                <TotpCodeDialog
                    action={changing}
                    onClose={closed}
                    onDisabled={() => {
                        closed();
                        toast({ description: t('STAFF.MFA.DISABLE.DONE') });
                    }}
                />
            )}
        </section>
    );
}

'use client';

import React, { useEffect, useRef, useState } from 'react';

import CodeEntry from '@app/components/mfa/code-entry';
import { mfaErrorText } from '@app/components/mfa/error-text';
import { useMfaT } from '@app/components/mfa/use-mfa-t';
import { Button } from '@app/shadcn/components/ui/button';
import { usePostMfaChallengeMutation, useVerifyMfaMutation } from '@app/store/auth/api';
import { mfaFailureOf, normaliseCode } from '@app/utils/mfa';

/**
 * The second step of signing in, for an account with an authenticator app: the
 * six-digit code, or one recovery code. The first step (the email code or
 * Google) left a short-lived challenge cookie; no session exists until this
 * succeeds. After too many wrong codes the server locks this step for a
 * while (429): the form says for how long and stays disabled until then. A
 * challenge that ran out (five minutes) or was used sends the person back to
 * the first step.
 */
export default function MfaCodeForm({
    onSignedIn,
    onBack,
    session = false,
    heading,
    intro,
    backLabel
}: {
    onSignedIn: () => void;
    onBack: () => void;
    // the session is already signed in and a workspace asks it for the second factor (the verify page), instead of the second step of a sign-in
    session?: boolean;
    // words of the caller's own for the title, the introduction and the way back (already translated)
    heading?: string;
    intro?: string;
    backLabel?: string;
}) {
    const { t, language } = useMfaT();
    const [challenge, challengeState] = usePostMfaChallengeMutation();
    const [verify, verifyState] = useVerifyMfaMutation();
    const isLoading = challengeState.isLoading || verifyState.isLoading;
    const [code, setCode] = useState('');
    const [recovery, setRecovery] = useState(false);
    const [error, setError] = useState('');
    const [expired, setExpired] = useState(false);
    const [locked, setLocked] = useState(false);
    const unlock = useRef<ReturnType<typeof setTimeout>>(undefined);

    useEffect(() => () => clearTimeout(unlock.current), []);

    const submit = async (event: React.FormEvent) => {
        event.preventDefault();
        const typed = normaliseCode(code, recovery);
        if (!typed || locked) return;
        setError('');
        const answer = await (session ? verify({ code: typed }) : challenge({ code: typed }));
        if ('data' in answer && answer.data) {
            onSignedIn();
            return;
        }
        const refused = mfaFailureOf((answer as { error?: unknown }).error);
        setCode('');
        if (!session && (refused.code === 'mfa_challenge_expired' || refused.code === 'no_factor' || refused.code === 'totp_off')) {
            setExpired(true);
            setError(mfaErrorText(t, refused));
            return;
        }
        if (refused.status === 429) {
            // locked: nothing more can be tried until the server's time is up
            setLocked(true);
            clearTimeout(unlock.current);
            unlock.current = setTimeout(
                () => {
                    setLocked(false);
                    setError('');
                },
                (refused.retryAfter ?? 15 * 60) * 1000
            );
        }
        setError(mfaErrorText(t, refused));
    };

    return (
        <form onSubmit={submit} lang={language} className="flex w-full flex-col gap-4" noValidate aria-labelledby="mfa-title">
            <h2 id="mfa-title" className="text-base font-semibold text-black-900">
                {!expired && !locked && heading ? heading : t(expired ? 'STAFF.MFA.SIGNIN.EXPIRED_TITLE' : locked ? 'STAFF.MFA.SIGNIN.LOCKED_TITLE' : session ? 'STAFF.MFA.VERIFY.TITLE' : 'STAFF.MFA.SIGNIN.TITLE')}
            </h2>
            {/* while locked the message under the field says what matters */}
            <p id="mfa-intro" hidden={locked} className="text-sm leading-relaxed text-black-700">
                {!recovery && intro ? intro : t(recovery ? 'STAFF.MFA.SIGNIN.INTRO_RECOVERY' : session ? 'STAFF.MFA.VERIFY.INTRO' : 'STAFF.MFA.SIGNIN.INTRO')}
            </p>

            {expired ? (
                <p role="alert" className="text-sm leading-relaxed font-medium text-[#B42318]">
                    {error}
                </p>
            ) : (
                <>
                    <CodeEntry
                        key={recovery ? 'recovery' : 'digits'}
                        id="mfa-code"
                        value={code}
                        recovery={recovery}
                        onChange={(value) => {
                            setCode(value);
                            if (!locked) setError('');
                        }}
                        error={error}
                        autoFocus
                        disabled={isLoading || locked}
                        describedBy="mfa-intro"
                    />
                    <button
                        type="button"
                        disabled={locked}
                        className="w-fit text-sm font-medium text-brand-600 underline underline-offset-2 hover:text-brand-700 disabled:opacity-50"
                        onClick={() => {
                            setRecovery(!recovery);
                            setCode('');
                            setError('');
                        }}
                    >
                        {t(recovery ? 'STAFF.MFA.CODE.USE_APP' : 'STAFF.MFA.CODE.USE_RECOVERY')}
                    </button>
                </>
            )}

            <div className="mt-2 flex flex-col gap-3">
                {!expired && (
                    <Button type="submit" variant="primary" size="medium" isLoading={isLoading} disabled={!code.trim() || locked} className="w-full">
                        {t(session ? 'STAFF.MFA.VERIFY.SUBMIT' : 'STAFF.MFA.SIGNIN.SUBMIT')}
                    </Button>
                )}
                <Button type="button" variant={expired ? 'primary' : 'ghost'} size="medium" className="w-full" onClick={onBack}>
                    {backLabel ?? t(session ? 'STAFF.MFA.VERIFY.BACK' : 'STAFF.MFA.SIGNIN.BACK')}
                </Button>
            </div>
        </form>
    );
}

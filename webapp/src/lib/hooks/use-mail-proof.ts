'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useIssueMailChallengeMutation } from '@app/store/redux/form-api';
import { CaptchaTurnedOff, MAIL_PROOF_BUSY, MailAnswer, MailScope, sendWithMailProof } from '@app/utils/captcha/mail-proof';
import { CaptchaChallenge } from '@app/utils/captcha/solver-core';

/**
 * The automatic spam check before a mail, from a form's side (utils/captcha/mail-proof):
 * `send(request)` makes the request and, when the server asks for a proof, solves one
 * and sends again. `waiting` turns on when that takes more than 1.5 seconds, so the
 * page can say so politely. Nothing is stored on the device.
 *
 * One mail at a time: while a request (and the solve before it) is under way, a second
 * call does nothing and answers `MAIL_PROOF_BUSY` (a double click must not send two
 * mails). The guard is a ref, so it holds between two presses in the same frame, before
 * any render; `busy` is the same fact for the page to show (a disabled button).
 */
export function useMailProof(scope: MailScope) {
    const [issue] = useIssueMailChallengeMutation();
    const [waiting, setWaiting] = useState(false);
    const [busy, setBusy] = useState(false);
    const inFlight = useRef(false);
    // the trigger changes identity every render; the fetcher keeps the latest
    const issueRef = useRef(issue);
    useEffect(() => {
        issueRef.current = issue;
    });
    const { workspaceId, formId } = scope;

    const send = useCallback(
        async <R extends MailAnswer>(request: (headers?: Record<string, string>) => Promise<R>) => {
            if (inFlight.current) return MAIL_PROOF_BUSY;
            inFlight.current = true;
            setBusy(true);
            try {
                const fetcher = async (): Promise<CaptchaChallenge> => {
                    const answer: any = await issueRef.current({ workspaceId, formId });
                    if (answer?.error?.status === 404 && answer.error.data?.code === 'captcha_off') throw new CaptchaTurnedOff();
                    if (!answer?.data?.challenge) throw new Error('No challenge');
                    return answer.data;
                };
                return await sendWithMailProof({ workspaceId, formId }, fetcher, request, { onSlow: () => setWaiting(true), onDone: () => setWaiting(false) });
            } finally {
                inFlight.current = false;
                setBusy(false);
            }
        },
        [workspaceId, formId]
    );

    return { send, waiting, busy };
}

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useIssueMailChallengeMutation } from '@app/store/redux/form-api';
import { CaptchaChallenge } from '@app/utils/captcha/solver-core';
import { MailAnswer, MailScope, sendWithMailProof } from '@app/utils/captcha/mail-proof';

/**
 * The automatic spam check before a mail, from a form's side (utils/captcha/mail-proof):
 * `send(request)` makes the request and, when the server asks for a proof, solves one
 * and sends again. `waiting` turns on when that takes more than 1.5 seconds, so the page
 * can say so politely. Nothing is stored on the device.
 */
export function useMailProof(scope: MailScope) {
    const [issue] = useIssueMailChallengeMutation();
    const [waiting, setWaiting] = useState(false);
    // the trigger changes identity every render; the fetcher keeps the latest
    const issueRef = useRef(issue);
    useEffect(() => {
        issueRef.current = issue;
    });
    const { workspaceId, formId } = scope;

    const send = useCallback(
        <R extends MailAnswer>(request: (headers?: Record<string, string>) => Promise<R>) => {
            const fetcher = async (): Promise<CaptchaChallenge> => {
                const answer: any = await issueRef.current({ workspaceId, formId });
                if (!answer?.data?.challenge) throw new Error('No challenge');
                return answer.data;
            };
            return sendWithMailProof({ workspaceId, formId }, fetcher, request, { onSlow: () => setWaiting(true), onDone: () => setWaiting(false) });
        },
        [workspaceId, formId]
    );

    return { send, waiting };
}

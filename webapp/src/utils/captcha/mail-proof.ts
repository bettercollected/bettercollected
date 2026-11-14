import { isCaptchaRefused } from '@app/utils/server-answer-errors';

import { CaptchaPass, ChallengeFetcher, captchaPassFor } from './captcha-pass';
import { CAPTCHA_HEADER } from './solver-core';

/**
 * The automatic spam check before a mail is sent (backend services/captcha,
 * purpose "mail"): the sign-in code of a respondent (a workspace) and of a creator
 * (no workspace), and the link of a draft (a form). The server asks only while its
 * CAPTCHA_ENABLED switch is on, and the page learns that from the server itself:
 * the first request goes out without a proof; if the server refuses it for the spam
 * check (422 `captcha_missing`), the page solves one and sends again, once. A page
 * served by a server with the check off therefore makes no extra request and loads
 * no worker, exactly as before. Once a scope is known to ask, later requests solve
 * first. Nothing is stored on the device.
 */

/** What a mail request answers with: an RTK Query result. */
export interface MailAnswer {
    data?: unknown;
    error?: unknown;
}

/** The scope of a mail: a workspace (none for the creator's code) and, for a draft link, the form. */
export interface MailScope {
    workspaceId?: string;
    formId?: string;
}

/** The synthetic answer when the browser cannot calculate the proof (never a server answer). */
export const MAIL_PROOF_FAILED = { error: { status: 0, data: { code: 'captcha_failed' } } };

/** What `useMailProof().send` answers when a mail is already being sent: nothing was done, so the page does nothing either. */
export const MAIL_PROOF_BUSY = { busy: true } as const;

export const isMailProofBusy = (answer: unknown): boolean => answer === MAIL_PROOF_BUSY;

export const isMailProofFailed = (error: any): boolean => error?.status === 0 && error?.data?.code === 'captcha_failed';

const asked = new Set<string>();

export const mailScopeKey = ({ workspaceId, formId }: MailScope) => `${workspaceId || 'creator'}:${formId || '-'}`;

/** For tests. */
export function resetMailProofKnowledge(): void {
    asked.clear();
}

export interface MailProofOptions {
    /** Called when the wait for the proof passes the pass's slow threshold. */
    onSlow?: () => void;
    /** Called when the wait for a proof ends, either way. */
    onDone?: () => void;
    /** For tests: the proofs of this scope. */
    pass?: CaptchaPass;
}

/**
 * Send a mail request, with the proof of work when the server asks for one.
 * `send(headers)` makes the request (headers only when there is a proof) and
 * answers as RTK Query does; `fetcher` asks for a challenge. A request is sent
 * at most twice: a refused proof (or none) is followed by one more with a new proof.
 */
export async function sendWithMailProof<R extends MailAnswer>(scope: MailScope, fetcher: ChallengeFetcher, send: (headers?: Record<string, string>) => Promise<R>, options: MailProofOptions = {}): Promise<R | typeof MAIL_PROOF_FAILED> {
    const key = mailScopeKey(scope);
    const pass = options.pass ?? captchaPassFor(`mail:${scope.workspaceId || 'creator'}`, scope.formId || '-');
    let needsProof = asked.has(key);
    let answer: R | undefined;
    for (let attempt = 0; attempt < 2; attempt++) {
        let headers: Record<string, string> | undefined;
        if (needsProof) {
            try {
                // a proof is single use: always a new one
                headers = { [CAPTCHA_HEADER]: await pass.take(fetcher, { fresh: true, onSlow: options.onSlow, onDone: options.onDone }) };
            } catch {
                return MAIL_PROOF_FAILED;
            }
        }
        answer = await send(headers);
        if (!isCaptchaRefused((answer as MailAnswer)?.error)) return answer;
        asked.add(key);
        needsProof = true;
    }
    return answer as R;
}

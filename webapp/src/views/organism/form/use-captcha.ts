'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useIssueCaptchaChallengeMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { captchaPassFor } from '@app/utils/captcha/captcha-pass';
import { CaptchaChallenge } from '@app/utils/captcha/solver-core';

/** The respondent's first interaction with the page: the calculation starts then, not on page load. */
const FIRST_INTERACTION = ['pointerdown', 'keydown', 'touchstart', 'focusin'] as const;

/**
 * The automatic spam check, from the form page's side (backend services/captcha):
 * while the server asks for it (`settings.captchaRequired`, never in the builder's
 * preview) the browser solves a proof of work in the background after the
 * respondent's first interaction, and `take` hands out one single-use proof for
 * the submit. `waiting` turns on when that takes more than 1.5 seconds, so the
 * page can say so politely. Nothing is stored on the device.
 */
export function useCaptcha(isPreviewMode: boolean) {
    const standardForm = useAppSelector(selectResponderForm);
    const workspace = useAppSelector(selectWorkspace);
    const [issue] = useIssueCaptchaChallengeMutation();
    const [waiting, setWaiting] = useState(false);
    // from asking for the proof until it is in hand: the button is not pressable twice meanwhile
    const [preparing, setPreparing] = useState(false);
    const workspaceId = workspace?.id;
    const formId = standardForm?.formId;
    const required = !isPreviewMode && standardForm?.settings?.captchaRequired === true && !!workspaceId && !!formId;

    // the trigger changes identity every render; the pass keeps the latest
    const issueRef = useRef(issue);
    useEffect(() => {
        issueRef.current = issue;
    });
    const fetcher = useCallback(async (): Promise<CaptchaChallenge> => {
        const answer: any = await issueRef.current({ workspaceId: workspaceId!, formId: formId! });
        if (!answer?.data?.challenge) throw new Error('No challenge');
        return answer.data;
    }, [workspaceId, formId]);

    useEffect(() => {
        if (!required) return;
        const pass = captchaPassFor(workspaceId!, formId!);
        const start = () => {
            FIRST_INTERACTION.forEach((name) => document.removeEventListener(name, start, true));
            pass.warm(fetcher);
        };
        FIRST_INTERACTION.forEach((name) => document.addEventListener(name, start, { capture: true, passive: true }));
        return () => FIRST_INTERACTION.forEach((name) => document.removeEventListener(name, start, true));
    }, [required, workspaceId, formId, fetcher]);

    const take = useCallback(
        (fresh = false) => {
            setPreparing(true);
            return captchaPassFor(workspaceId!, formId!).take(fetcher, {
                fresh,
                onSlow: () => setWaiting(true),
                onDone: () => {
                    setWaiting(false);
                    setPreparing(false);
                }
            });
        },
        [workspaceId, formId, fetcher]
    );

    return { required, take, waiting, preparing };
}

'use client';

import React, { Dispatch, SetStateAction, useEffect, useState } from 'react';

import { useSearchParams } from 'next/navigation';
import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { usePostSendOtpMutation, usePostVerifyOtpMutation } from '@app/store/auth/api';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { browserMailLocale } from '@app/utils/mail-locale';
import { reloadPage } from '@app/utils/browser-navigation';
import { isMfaRequired } from '@app/utils/mfa';
import { isMailProofBusy, isMailProofFailed } from '@app/utils/captcha/mail-proof';
import { codeMailRetryAfter, codeMailUnavailableMessage, isCaptchaRefused, isCodeMailUnavailable, isRateLimited } from '@app/utils/server-answer-errors';
import MailProofStatus from '@app/components/captcha/mail-proof-status';
import { useMailProof } from '@app/lib/hooks/use-mail-proof';

import MfaCodeForm from '@app/components/mfa/mfa-code-form';

interface OtpCodeFormProps {
    email: string;
    isModal?: boolean;
    setEmail: Dispatch<SetStateAction<string>>;
    // told when the sign-in turns out to need a second factor (true) and when the person goes back (false)
    onMfaChange?: (active: boolean) => void;
}

export default function OtpCodeForm({ email, isModal, setEmail: setParentEmail, onMfaChange }: OtpCodeFormProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const { closeModal } = useFullScreenModal();
    const [otp, setOtp] = useState('');
    const [counter, setCounter] = useState(60);
    const [isError, setIsError] = useState(false);
    // an account with an authenticator app: the email code was the first step
    const [secondFactor, setSecondFactor] = useState(false);

    useEffect(() => {
        if (counter > 0) {
            const timer = setTimeout(() => setCounter(counter - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [counter]);

    const [postVerifyOtp, { isLoading }] = usePostVerifyOtpMutation();
    const [postSendOtp] = usePostSendOtpMutation();
    const { language: respondentLanguage } = useRespondentLanguage();
    const searchParams = useSearchParams();
    const fromProPlan = searchParams?.get('fromProPlan');
    const workspace_id = searchParams?.get('workspace_id');
    // The automatic spam check before the next code mail, when the server asks for it (utils/captcha/mail-proof)
    const { send: sendWithProof, waiting: proofWaiting, busy: proofBusy } = useMailProof({ workspaceId: workspace_id || undefined });

    const constants = {
        otpVerificationSuccess: t(formResponderLogin.verificationSuccessMessage),
        otpVerificationFailure: t(formResponderLogin.verificationFailureMessage),
        enterOtpCode: t(signInScreen.enterOtpCode),
        enterOtpCodePlaceholder: t(signInScreen.enterOtpCodePlaceholder),
        didnotReceiveCode: t(signInScreen.didNotReceiveCode),
        signInButton: t(signInScreen.signInButton),
    };

    const signedIn = () => {
        toast({ description: constants.otpVerificationSuccess });
        closeModal();
        if (typeof window !== 'undefined') {
            reloadPage();
        }
    };

    const handleOtpPost = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!otp) return;

        const data = {
            body: { email, otp_code: otp },
            // the workspace whose forms the code was asked for: an address
            // whose domain requires SSO elsewhere gets a respondent-only
            // session here (docs/sso.md)
            params: { prospective_pro_user: Boolean(fromProPlan), ...(workspace_id ? { workspace_id } : {}) }
        };
        const res = await postVerifyOtp(data);

        if ('data' in res && isMfaRequired(res.data)) {
            // no session yet: the second step makes it
            setSecondFactor(true);
            onMfaChange?.(true);
        } else if ('data' in res && !!res.data) {
            signedIn();
        } else {
            setIsError(true);
            toast({ description: constants.otpVerificationFailure, variant: 'destructive' });
        }
    };

    const resendOtpCode = async () => {
        // the same language as the first code (otp-email-form)
        const locale = workspace_id ? respondentLanguage : browserMailLocale();
        const res: any = await sendWithProof((headers) => postSendOtp({ receiver_email: email, workspace_id: workspace_id || '', locale, ...(headers ? { headers } : {}) }));
        // a second press while the first is being solved or sent does nothing
        if (isMailProofBusy(res)) return;
        if ('data' in res && !!res.data) {
            setCounter(60);
        } else if (isMailProofFailed((res as any)?.error) || isCaptchaRefused((res as any)?.error)) {
            toast({ description: t(formResponderLogin.otpCaptchaFailedMessage), variant: 'destructive' });
        } else if (isCodeMailUnavailable((res as any)?.error)) {
            // no code was sent: say so, and keep Resend closed for the wait the server names
            toast({ description: codeMailUnavailableMessage((res as any).error, (seconds) => t(formResponderLogin.otpUnavailableMessage, { seconds })), variant: 'destructive' });
            setCounter(codeMailRetryAfter((res as any).error));
        } else if (isRateLimited((res as any)?.error)) {
            toast({ description: t(formResponderLogin.otpRateLimitedMessage), variant: 'destructive' });
        }
    };

    if (secondFactor) {
        return (
            <MfaCodeForm
                onSignedIn={signedIn}
                onBack={() => {
                    onMfaChange?.(false);
                    setParentEmail('');
                }}
            />
        );
    }

    return (
        <form onSubmit={handleOtpPost} className="w-full">
            <p className="text-black-900 mb-1 text-base font-semibold">{constants.enterOtpCode}</p>
            {/* Say where the code went and offer a way back — a mistyped email
                was a dead end (the only recovery was reloading the page). */}
            <p className="text-black-700 mb-3 text-sm">
                We emailed a 6-digit code to <span className="font-medium">{email}</span>.{' '}
                <button type="button" className="text-brand-500 hover:text-brand-600 underline underline-offset-2" onClick={() => setParentEmail('')}>
                    Change email
                </button>
            </p>
            <Input
                autoFocus
                placeholder={constants.enterOtpCodePlaceholder}
                value={otp}
                onChange={(e) => {
                    setOtp(e.target.value);
                    setIsError(false);
                }}
                className={isError ? 'border-[#C43D3D]' : ''}
            />

            <div className="mt-8 flex items-center justify-between text-base">
                <p className="text-black-900 font-normal">{constants.didnotReceiveCode}</p>
                <button
                    type="button"
                    onClick={resendOtpCode}
                    disabled={counter > 0 || proofBusy}
                    aria-disabled={counter > 0 || proofBusy}
                    aria-busy={proofBusy || undefined}
                    className={`font-semibold ${counter === 0 && !proofBusy ? 'cursor-pointer text-brand-500 hover:text-brand-600' : 'cursor-not-allowed text-black-600'}`}
                >
                    Resend {counter > 0 ? `(${counter}s)` : ''}
                </button>
            </div>
            <MailProofStatus waiting={proofWaiting} text={t(formResponderLogin.otpCaptchaWaitingMessage)} />

            <Button
                type="submit"
                variant="primary"
                isLoading={isLoading}
                className="mt-6 w-full"
                size="medium"
            >
                {constants.signInButton}
            </Button>
        </form>
    );
}

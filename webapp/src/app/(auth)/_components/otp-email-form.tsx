'use client';

import React, { Dispatch, SetStateAction, useState } from 'react';

import { useSearchParams } from 'next/navigation';

import ConnectWithProviderButton from '@Components/login/login-with-google-button';
import { useTranslation } from 'react-i18next';

import environments from '@app/configs/environments';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import { useSsoEnabled } from '@app/shared/hocs/runtime-flags-provider';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';
import { Separator } from '@app/shadcn/components/ui/separator';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { usePostSendOtpMutation } from '@app/store/auth/api';
import { capitalize } from '@app/utils/string-utils';

import SsoSignIn from './sso-sign-in';

interface OtpEmailFormProps {
    isModal?: boolean;
    isSignup?: string | boolean;
    setEmail: Dispatch<SetStateAction<string>>;
}

const providers: Array<string> = ['google'];

const loginProviderNames = new Map<string, string>([
    ['google', 'Google'],
    ['typeform', 'Typeform']
]);

export default function OtpEmailForm({ isModal, isSignup, setEmail: setParentEmail }: OtpEmailFormProps) {
    const ssoEnabled = useSsoEnabled();
    const { t } = useTranslation();
    const { toast } = useToast();
    const [postSendOtp, { isLoading }] = usePostSendOtpMutation();
    const [email, setEmail] = useState('');
    const searchParams = useSearchParams();
    const fromProPlan = searchParams?.get('fromProPlan');
    const type = searchParams?.get('type');
    const isCreator = type !== 'responder';
    const workspace_id = searchParams?.get('workspace_id');
    // Set by the backend when a provider sign-in was refused (#758). Anyone can
    // craft these params, so only known codes and provider names are shown.
    const loginError = searchParams?.get('login_error');
    const loginProvider = loginProviderNames.get(searchParams?.get('login_provider') ?? '') ?? 'Your sign-in provider';
    const loginErrorMessage =
        loginError === 'unverified_email'
            ? `${loginProvider} couldn't confirm that this email address is yours, so we didn't sign you in. Sign in with a code sent to your email instead.`
            : loginError === 'sso_required'
              ? `Your organisation requires single sign-on for this email address, so we didn't sign you in with ${loginProvider}. Use “Sign in with SSO” below.`
              : null;
    // set when an email code was refused because the address's domain
    // requires single sign-on: the SSO form opens with the email filled in
    const [ssoNotice, setSsoNotice] = useState<{ email: string; message: string } | null>(null);
    const constants = {
        welcomeBack: t(signInScreen.welcomeBack),
        signUp: t(signUpScreen.signUp),
        signInToContinue: t(signInScreen.signInToContinue),
        orSignInUsing: t(signInScreen.orSignInUsing),
        emailInputLabel: t(signInScreen.emailInputLabel),
        enterYourEmail: t(signInScreen.enterYourEmail),
        sendCodeButton: t(signInScreen.sendCodeButton),
        descriptionInModal: t(signInScreen.descriptionInModal),
        signUpToContinue: t(signUpScreen.signUpToContinue),
        otpSuccessMessage: t(formResponderLogin.otpSuccessMessage),
        otpFailureMessage: t(formResponderLogin.otpFailureMessage)
    };

    const handleEmailInputForCreator = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!email) return;

        const res = await postSendOtp({ receiver_email: email, workspace_id: workspace_id || '' });

        if ('data' in res && !!res.data) {
            toast({ description: constants.otpSuccessMessage });
            setParentEmail(email);
        } else if (ssoEnabled && !isModal && (res as any)?.error?.data?.code === 'sso_required') {
            setSsoNotice({ email, message: (res as any).error.data.message });
        } else if ((res as any)?.error?.data?.code === 'sso_required') {
            toast({ description: (res as any).error.data.message, variant: 'destructive' });
        } else {
            toast({ description: constants.otpFailureMessage, variant: 'destructive' });
        }
    };

    return (
        <div className="w-full">
            <form className={`w-full ${isModal ? 'mt-16' : ''}`} onSubmit={handleEmailInputForCreator}>
                {loginErrorMessage && (
                    <p role="alert" className="body4 mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 !text-red-700">
                        {loginErrorMessage}
                    </p>
                )}
                <div className="flex flex-col gap-3">
                    <span className="h4">{isSignup || isModal ? constants.signUp : constants.welcomeBack}</span>
                    {isModal ? <span className="body4 sm:w-[410px]">{constants.descriptionInModal}</span> : <span className="body4 text-black-800">{isSignup ? constants.signUpToContinue : constants.signInToContinue}</span>}
                </div>

                {providers.length > 0 && (
                    <>
                        <div className="mt-10 flex w-full gap-[20px]">
                            <div className="flex w-full flex-col items-center justify-center gap-4 sm:flex-row lg:gap-6">
                                {providers.map((provider) => (
                                    <ConnectWithProviderButton key={provider} type="dark" url={`${environments.API_ENDPOINT_HOST}/auth/${provider}/basic`} text={`Sign in with ${capitalize(provider)}`} creator={isCreator} fromProPlan={fromProPlan!} />
                                ))}
                            </div>
                        </div>
                        <div className="my-10 flex w-full items-center gap-4 pt-8">
                            <Separator className="flex-1 shrink-0 bg-black-200" />
                            <span className="body4 whitespace-nowrap !text-black-700">{constants.orSignInUsing}</span>
                            <Separator className="flex-1 shrink-0 bg-black-200" />
                        </div>
                    </>
                )}

                <p className="mb-3 mt-[44px] text-base font-semibold text-black-900">{constants.emailInputLabel}</p>
                <Input autoFocus type="email" required placeholder={constants.enterYourEmail} value={email} onChange={(e) => setEmail(e.target.value)} className="!text-base lg:!text-base" />
                <Button type="submit" variant="primary" isLoading={isLoading} className={`mt-6 w-full ${isModal ? 'mb-10' : ''}`} size="medium">
                    {constants.sendCodeButton}
                </Button>
            </form>
            {ssoEnabled && !isModal && (
                <div className="mt-6 w-full">
                    <SsoSignIn key={ssoNotice?.email ?? ''} initialEmail={ssoNotice?.email} notice={ssoNotice?.message} />
                </div>
            )}
        </div>
    );
}

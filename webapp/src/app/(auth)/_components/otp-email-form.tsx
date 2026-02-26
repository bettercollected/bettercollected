'use client';

import React, { Dispatch, SetStateAction, useState } from 'react';

import { useSearchParams } from 'next/navigation';
import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';
import { Separator } from '@app/shadcn/components/ui/separator';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import ConnectWithProviderButton from '@Components/login/login-with-google-button';
import environments from '@app/configs/environments';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import { usePostSendOtpMutation } from '@app/store/auth/api';
import { capitalize } from '@app/utils/string-utils';

interface OtpEmailFormProps {
    isModal?: boolean;
    isSignup?: string | boolean;
    setEmail: Dispatch<SetStateAction<string>>;
}

const providers: Array<string> = ["google"];

export default function OtpEmailForm({ isModal, isSignup, setEmail: setParentEmail }: OtpEmailFormProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [postSendOtp, { isLoading }] = usePostSendOtpMutation();
    const [email, setEmail] = useState('');
    const searchParams = useSearchParams();
    const fromProPlan = searchParams?.get('fromProPlan');
    const type = searchParams?.get('type');
    const isCreator = type !== 'responder';
    const workspace_id = searchParams?.get('workspace_id');
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

        const res = await postSendOtp({ receiver_email: email, workspace_id: workspace_id || "" });

        if ('data' in res && !!res.data) {
            toast({ description: constants.otpSuccessMessage });
            setParentEmail(email);
        } else {
            toast({ description: constants.otpFailureMessage, variant: 'destructive' });
        }
    };

    return (
        <form className={`w-full ${isModal ? 'mt-16' : ''}`} onSubmit={handleEmailInputForCreator}>
            <div className="flex flex-col gap-3">
                <span className="h4">{isSignup || isModal ? constants.signUp : constants.welcomeBack}</span>
                {isModal ? (
                    <span className="body4 sm:w-[410px]">{constants.descriptionInModal}</span>
                ) : (
                    <span className="body4 text-black-800">{isSignup ? constants.signUpToContinue : constants.signInToContinue}</span>
                )}
            </div>

            {providers.length > 0 && (
                <>
                    <div className="mt-10 flex w-full gap-[20px]">
                        <div className="flex w-full flex-col items-center justify-center gap-4 sm:flex-row lg:gap-6">
                            {providers.map((provider) => (
                                <ConnectWithProviderButton
                                    key={provider}
                                    type="dark"
                                    url={`${environments.API_ENDPOINT_HOST}/auth/${provider}/basic`}
                                    text={`Sign in with ${capitalize(provider)}`}
                                    creator={isCreator}
                                    fromProPlan={fromProPlan!}
                                />
                            ))}
                        </div>
                    </div>
                    <div className="flex w-full items-center gap-4 my-10 pt-8">
                        <Separator className="flex-1 shrink-0 bg-black-200" />
                        <span className="body4 !text-black-700 whitespace-nowrap">{constants.orSignInUsing}</span>
                        <Separator className="flex-1 shrink-0 bg-black-200" />
                    </div>
                </>
            )}

            <p className="text-black-900 mb-3 mt-[44px] text-base font-semibold">{constants.emailInputLabel}</p>
            <Input
                autoFocus
                type="email"
                required
                placeholder={constants.enterYourEmail}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="!text-base lg:!text-base"
            />
            <Button
                type="submit"
                variant="primary"
                isLoading={isLoading}
                className={`mt-6 w-full ${isModal ? 'mb-10' : ''}`}
                size="medium"
            >
                {constants.sendCodeButton}
            </Button>
        </form>
    );
}

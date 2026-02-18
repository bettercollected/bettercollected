'use client';

import React, { Dispatch, SetStateAction, useState } from 'react';

import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'next/navigation';

import { Input } from '@app/shadcn/components/ui/input';
import { Button } from '@app/shadcn/components/ui/button';
import { Divider } from '@mui/material'; // I'll keep Divider from MUI for now, or use a custom one if available
import { useToast } from '@app/shadcn/components/ui/use-toast';

import ConnectWithProviderButton from '@app/Components/Login/login-with-google-button';
import environments from '@app/configs/environments';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import { usePostSendOtpForCreatorMutation } from '@app/store/auth/api';
import { capitalize } from '@app/utils/stringUtils';

interface OtpEmailFormProps {
    isModal?: boolean;
    isSignup?: string | boolean;
    setEmail: Dispatch<SetStateAction<string>>;
}

const providers: Array<string> = [];
if (environments.ENABLE_GOOGLE) providers.push('google');

export default function OtpEmailForm({ isModal, isSignup, setEmail: setParentEmail }: OtpEmailFormProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [postSendOtpForCreator, { isLoading }] = usePostSendOtpForCreatorMutation();
    const [email, setEmail] = useState('');
    const searchParams = useSearchParams();
    const fromProPlan = searchParams?.get('fromProPlan');

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

        const res = await postSendOtpForCreator({ receiver_email: email });

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
                                    creator={true}
                                    fromProPlan={fromProPlan!}
                                />
                            ))}
                        </div>
                    </div>
                    <Divider orientation="horizontal" flexItem className="body4 !text-black-700 pt-8 my-10">
                        {constants.orSignInUsing}
                    </Divider>
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
                className="!text-base lg:!text-base" // Overriding the default large text in ShadCNInput if it's too big
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

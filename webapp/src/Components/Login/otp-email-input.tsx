import React, { Dispatch, SetStateAction, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import Divider from '@mui/material/Divider';
import { toast } from 'react-toastify';

import ConnectWithProviderButton from '@app/Components/Login/login-with-google-button';
import environments from '@app/configs/environments';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import { usePostSendOtpForCreatorMutation, usePostSendOtpMutation } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';
import { capitalize } from '@app/utils/stringUtils';

interface OtpEmailInputPropType {
    isCreator: boolean;
    isModal?: boolean;
    isSignup?: string | string[] | undefined;
    setEmail: Dispatch<SetStateAction<string>>;
    workspaceId?: string;
}

const providers: Array<string> = [];
if (environments.ENABLE_GOOGLE) providers.push('google');
// if (environments.ENABLE_TYPEFORM) providers.push('typeform');

export default function OtpEmailInput(props: OtpEmailInputPropType) {
    const { isCreator, isModal, isSignup } = props;

    const workspace = useAppSelector((state) => state.workspace);

    const { t } = useTranslation();

    const [postSendOtp, { isLoading }] = usePostSendOtpMutation();

    const [postSendOtpForCreator, creatorResponse] = usePostSendOtpForCreatorMutation();

    const [email, setEmail] = useState('');

    const { fromProPlan } = useRouter().query;

    const constants = {
        welcomeBack: t(signInScreen.welcomeBack),
        signUp: t(signUpScreen.signUp),
        signInToContinue: t(signInScreen.signInToContinue),
        heading3: t(signInScreen.signIn),
        subHeading2: t(signInScreen.continueWIth),
        button: t(signInScreen.signUp),
        enterYourEmail: t(signInScreen.enterYourEmail),
        orSignInUsing: t(signInScreen.orSignInUsing),
        verificationTitle: t(signInScreen.verificationTitle),
        enterOtpCode: t(signInScreen.enterOtpCode),
        sendCodeButton: t(signInScreen.sendCodeButton),
        backButtonTitle: t(signInScreen.backButtonTitle),
        didnotReceiveCode: t(signInScreen.didNotReceiveCode),
        emailInputLabel: t(signInScreen.emailInputLabel),
        descriptionInModal: t(signInScreen.descriptionInModal),
        signUpToContinue: t(signUpScreen.signUpToContinue),
        otpSuccessMessage: t(formResponderLogin.otpSuccessMessage),
        otpFailureMessage: t(formResponderLogin.otpFailureMessage)
    };

    const handleEmailInput = (e: any) => {
        setEmail(e.target.value);
    };

    const handleResponseToast = (res: any) => {
        if (!!res?.data) {
            toast(constants.otpSuccessMessage, { type: 'success' });
            props.setEmail(email);
        } else {
            toast(constants.otpFailureMessage, { type: 'error' });
        }
    };

    const handleEmailInputForResponder = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!email) return;
        const req = {
            workspace_id: props.workspaceId ?? workspace.id,
            receiver_email: email
        };
        const res = await postSendOtp(req);
        handleResponseToast(res);
    };

    const handleEmailInputForCreator = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!email) return;
        const req = {
            receiver_email: email
        };
        const res = await postSendOtpForCreator(req);
        handleResponseToast(res);
    };
    return (
        <form className={` w-full ${isModal ? ' mt-16' : ''}`} onSubmit={isCreator ? handleEmailInputForCreator : handleEmailInputForResponder}>
            <div className="flex flex-col gap-3">
                {isCreator && <span className="h4 ">{isSignup || isModal ? constants.signUp : constants.welcomeBack}</span>}
                {!isCreator && <span className="p2-new text-black-700 w-full text-center">Verify your Email address</span>}

                {isCreator && <>{isModal ? <span className="body4 sm:w-[410px]">{constants.descriptionInModal}</span> : <span className="body4 text-black-800">{isSignup ? constants.signUpToContinue : constants.signInToContinue}</span>}</>}
            </div>
            {providers.length > 0 && (
                <>
                    <div className="mt-10 flex w-full gap-[20px]">
                        <div className="flex w-full flex-col items-center justify-center gap-4  sm:flex-row lg:gap-6">
                            {providers.map((provider: string) => (
                                <ConnectWithProviderButton key={provider} type={'dark'} url={`${environments.API_ENDPOINT_HOST}/auth/${provider}/basic`} text={`Sign in with ${capitalize(provider)}`} creator={isCreator} fromProPlan={fromProPlan} />
                            ))}
                        </div>
                    </div>
                    {isCreator && (
                        <Divider orientation="horizontal" flexItem className={'body4 !text-black-700 my-10'}>
                            {constants.orSignInUsing}
                        </Divider>
                    )}
                </>
            )}
            <p className="text-black-900 mb-3 mt-[44px] text-base font-semibold">{constants.emailInputLabel}</p>
            <AppTextField autoFocus type={'email'} required={true} placeholder={constants.enterYourEmail} value={email} onChange={handleEmailInput} />
            <AppButton type={'submit'} variant={ButtonVariant.Primary} isLoading={isCreator ? creatorResponse.isLoading : isLoading} className={`mt-6 w-full ${isModal ? 'mb-10' : ''}`} size={ButtonSize.Medium}>
                {constants.sendCodeButton}
            </AppButton>
        </form>
    );
}

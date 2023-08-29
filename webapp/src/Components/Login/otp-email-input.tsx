import React, { Dispatch, SetStateAction, useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@mui/material/Divider';
import { toast } from 'react-toastify';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import BetterInput from '@app/components/Common/input';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import { IntegrationFormProviders } from '@app/models/dtos/provider';
import { usePostSendOtpForCreatorMutation, usePostSendOtpMutation } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';
import { capitalize } from '@app/utils/stringUtils';

interface OtpEmailInputPropType {
    isCreator: boolean;
    isModal?: boolean;
    isSignup?: string | string[] | undefined;
    setEmail: Dispatch<SetStateAction<string>>;
}

export default function OtpEmailInput(props: OtpEmailInputPropType) {
    const { isCreator, isModal, isSignup } = props;

    const workspace = useAppSelector((state) => state.workspace);

    const { t } = useTranslation();

    const [postSendOtp, { isLoading }] = usePostSendOtpMutation();

    const [postSendOtpForCreator, creatorResponse] = usePostSendOtpForCreatorMutation();

    const [email, setEmail] = useState('');

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
            workspace_id: workspace.id,
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
                <span className="h4 ">{(isSignup || isModal) ? constants.signUp : constants.welcomeBack}</span>
                {isModal ? <span className="body4 sm:w-[410px]">{constants.descriptionInModal}</span> : <span className="body4 text-black-800">{isSignup ? constants.signUpToContinue : constants.signInToContinue}</span>}
            </div>
            <div className="flex gap-[20px] mt-10 w-full">
                <FormProviderContext.Consumer>
                    {(formProviders: Array<IntegrationFormProviders>) => (
                        <div className="flex flex-col sm:flex-row gap-4 lg:gap-6 w-full justify-center items-center">
                            {Array.from(formProviders)
                                .reverse()
                                .map((provider: IntegrationFormProviders) => (
                                    <ConnectWithProviderButton
                                        key={provider.providerName}
                                        type={provider.providerName === 'typeform' ? 'typeform' : 'dark'}
                                        url={`${environments.API_ENDPOINT_HOST}/auth/${provider.providerName}/basic`}
                                        text={`Sign in with ${capitalize(provider.providerName)}`}
                                        creator={isCreator}
                                    />
                                ))}
                        </div>
                    )}
                </FormProviderContext.Consumer>
            </div>

            <Divider orientation="horizontal" flexItem className={'body4 !text-black-700 my-10'}>
                {constants.orSignInUsing}
            </Divider>
            <p className="text-base font-semibold mb-3 mt-[44px] text-black-900">{constants.emailInputLabel}</p>
            <BetterInput type={'email'} required={true} placeholder={constants.enterYourEmail} value={email} onChange={handleEmailInput} />
            <Button type={'submit'} variant="solid" isLoading={isCreator ? creatorResponse.isLoading : isLoading} className={`body1 w-full mt-6 ${isModal ? 'mb-10' : ''}`} size={'extraMedium'}>
                {constants.sendCodeButton}
            </Button>
        </form>
    );
}

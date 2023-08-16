import React, { Dispatch, SetStateAction, useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@mui/material/Divider';
import { toast } from 'react-toastify';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { IntegrationFormProviders } from '@app/models/dtos/provider';
import { usePostSendOtpForCreatorMutation, usePostSendOtpMutation } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';
import { capitalize } from '@app/utils/stringUtils';

interface OtpEmailInputPropType {
    isCreator: boolean;
    isModal?: boolean;
    setEmail: Dispatch<SetStateAction<string>>;
}

export default function OtpEmailInput(props: OtpEmailInputPropType) {
    const { isCreator, isModal } = props;

    const workspace = useAppSelector((state) => state.workspace);

    const { t } = useTranslation();

    const [postSendOtp, { isLoading }] = usePostSendOtpMutation();

    const [postSendOtpForCreator, creatorResponse] = usePostSendOtpForCreatorMutation();

    const [email, setEmail] = useState('');

    const constants = {
        heading3: t(signInScreen.signIn),
        subHeading2: t(signInScreen.continueWIth),
        button: t(signInScreen.signUp),
        enterYourEmail: t(signInScreen.enterYourEmail),
        continue: t(signInScreen.continue),
        orSignInUsing: t(signInScreen.orSignInUsing),
        verificationTitle: t(signInScreen.verificationTitle),
        enterOtpCode: t(signInScreen.enterOtpCode),
        backButtonTitle: t(signInScreen.backButtonTitle),
        didnotReceiveCode: t(signInScreen.didNotReceiveCode),
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
        <form className={` w-full ${isModal ? 'mt-[48px]' : 'mt-[80px]'}`} onSubmit={isCreator ? handleEmailInputForCreator : handleEmailInputForResponder}>
            <div className="flex flex-col gap-3 mt-2">
                <span className="h4 ">{constants.heading3}</span>
                {isModal && <span className="body4 sm:w-[410px]">You will only be able to see responses done with the email you sign in with.</span>}
            </div>
            <p className="body4 mb-[8px] mt-[44px] text-black-900">{constants.enterYourEmail}</p>
            <input
                type={'email'}
                required={true}
                className={`body4 flex-1 px-4 py-3 w-full placeholder:font-normal placeholder:text-sm placeholder:tracking-normal !rounded-[1px] text-black-900 bg-white border-gray-400`}
                placeholder={constants.enterYourEmail}
                value={email}
                onChange={handleEmailInput}
            />
            <Button type={'submit'} variant="solid" isLoading={isCreator ? creatorResponse.isLoading : isLoading} className={'body1 w-full mt-[32px] mb-[44px]'} size={'extraMedium'}>
                {constants.continue}
            </Button>

            <Divider orientation="horizontal" flexItem className={'body4 !text-black-700 mb-[40px]'}>
                {constants.orSignInUsing}
            </Divider>

            <div className="flex flex-col gap-[20px] mb-[60px] w-full">
                <FormProviderContext.Consumer>
                    {(formProviders: Array<IntegrationFormProviders>) => (
                        <div className="flex md:flex-row flex-col gap-4 justify-center items-center">
                            {formProviders.map((provider: IntegrationFormProviders) => (
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
        </form>
    );
}

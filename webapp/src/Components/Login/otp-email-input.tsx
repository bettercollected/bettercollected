import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@mui/material/Divider';
import { toast } from 'react-toastify';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import BetterInput from '@app/components/Common/input';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { IntegrationFormProviders } from '@app/models/dtos/provider';
import { usePostSendOtpForCreatorMutation, usePostSendOtpMutation } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';
import { capitalize } from '@app/utils/stringUtils';

export default function OtpEmailInput(props: any) {
    const isCreator = props.isCreator;

    const workspace = useAppSelector((state) => state.workspace);

    const { t } = useTranslation();

    const [postSendOtp, { isLoading, isSuccess, isError }] = usePostSendOtpMutation();

    const [postSendOtpForCreator, creatorResponse] = usePostSendOtpForCreatorMutation();

    const [email, setEmail] = useState('');

    const [stepCount, setStepCount] = useState(0);

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
        didnotReceiveCode: t(signInScreen.didNotReceiveCode)
    };

    const handleEmailInput = (e: any) => {
        setEmail(e.target.value);
    };

    const handleResponseToast = (res: any) => {
        if (!!res?.data) {
            toast(res.data.message, { type: 'success' });
            props.setStepCount(stepCount + 1);
        } else {
            toast('Failed to send otp!', { type: 'error' });
        }
    };

    const handleEmailInputForResponder = async () => {
        if (!email) return;
        const req = {
            workspace_id: workspace.id,
            receiver_email: email
        };
        const res = await postSendOtp(req);
        handleResponseToast(res);
    };

    const handleEmailInputForCreator = async () => {
        if (!email) return;
        const req = {
            receiver_email: email
        };
        const res = await postSendOtpForCreator(req);
        handleResponseToast(res);
    };

    return (
        <div className="mt-[96px]">
            <h3 className="h3 mb-[16px]">{constants.heading3}</h3>

            <p className=" mb-[8px] mt-[44px] text-black-900">{constants.enterYourEmail}</p>
            <BetterInput placeholder={constants.enterYourEmail} value={email} onChange={handleEmailInput} />
            <Button variant="solid" isLoading={isCreator ? creatorResponse.isLoading : isLoading} className={'w-full mt-[32px] mb-[40px]'} size={'large'} onClick={isCreator ? handleEmailInputForCreator : handleEmailInputForResponder}>
                {constants.continue}
            </Button>

            <Divider orientation="horizontal" flexItem className={'text-black-700 mb-[40px]'}>
                {constants.orSignInUsing}
            </Divider>

            <div className="flex flex-col gap-[20px] mb-[60px]">
                <FormProviderContext.Consumer>
                    {(formProviders: Array<IntegrationFormProviders>) => (
                        <div className="flex md:flex-row flex-col gap-4">
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
        </div>
    );
}

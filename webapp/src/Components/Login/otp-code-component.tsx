import React, { Dispatch, SetStateAction, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import Back from '@app/components/icons/back';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { usePostSendOtpForCreatorMutation, usePostSendOtpMutation, usePostVerifyOtpMutation } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

interface OtpCodePropType {
    email: string;
    isCreator: boolean;
    isModal?: boolean;
    setEmail: Dispatch<SetStateAction<string>>;
}

export default function OtpCodeComponent(props: OtpCodePropType) {
    const { t } = useTranslation();

    const { isModal } = props;

    const { closeModal } = useFullScreenModal();

    const workspace = useAppSelector((state) => state.workspace);

    const router = useRouter();

    const [otp, setOtp] = useState('');
    const [counter, setCounter] = useState(60);

    useEffect(() => {
        counter > 0 && setTimeout(() => setCounter(counter - 1), 1000);
    }, [counter]);

    const [postVerifyOtp, { isLoading }] = usePostVerifyOtpMutation();
    const [postSendOtp] = usePostSendOtpMutation();
    const [postSendOtpForCreator] = usePostSendOtpForCreatorMutation();

    const constants = {
        subHeading2: t(signInScreen.continueWIth),
        button: t(signInScreen.signUp),
        enterYourEmail: t(signInScreen.enterYourEmail),
        continue: t(signInScreen.continue),
        orSignInUsing: t(signInScreen.orSignInUsing),
        verificationTitle: t(signInScreen.verificationTitle),
        enterOtpCode: t(signInScreen.enterOtpCode),
        backButtonTitle: t(signInScreen.backButtonTitle),
        didnotReceiveCode: t(signInScreen.didNotReceiveCode),
        otpVerificationSuccess: t(formResponderLogin.verificationSuccessMessage),
        otpVerificationFailure: t(formResponderLogin.verificationFailureMessage)
    };

    const handleOtpChange = (e: any) => {
        setOtp(e.target.value);
    };

    const handleGoBackOnStepOne = () => {
        props.setEmail('');
    };

    const handleResponseToast = async (res: any) => {
        if (!!res?.data) {
            toast(constants.otpVerificationSuccess, { type: 'success' });
            props.isCreator && closeModal();
            await router.reload();
        } else {
            toast(constants.otpVerificationFailure, { type: 'error' });
        }
    };

    const resendOtpCode = async () => {
        let res;
        if (props.isCreator) {
            const req = {
                receiver_email: props.email
            };
            res = await postSendOtpForCreator(req);
        } else {
            const req = {
                receiver_email: props.email,
                workspace_id: workspace.id
            };
            res = await postSendOtp(req);
        }
        // @ts-ignore
        if (!!res?.data) {
            setCounter(60);
        }
    };

    const handleOtpPost = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!otp) return;
        const req = {
            email: props.email,
            otp_code: otp
        };
        const res = await postVerifyOtp(req);
        await handleResponseToast(res);
    };

    return (
        <>
            <div className={`flex items-center cursor-pointer gap-1 hover:text-brand ${isModal ? 'mt-[44px]' : ' mt-[48px]'}`} onClick={handleGoBackOnStepOne}>
                <Back />
                <p className={'hover:text-brand'}>{constants.backButtonTitle}</p>
            </div>
            <h3 className={`h4 mb-4 ${isModal ? 'mt-5' : ' mt-[44px]'}`}>{constants.verificationTitle}</h3>

            <form onSubmit={handleOtpPost} className="w-full">
                <p className={`body4 mb-[8px] text-black-900 ${!isModal && 'mt-[44px]'}`}>{constants.enterOtpCode}</p>
                <BetterInput placeholder={constants.enterOtpCode} value={otp} onChange={handleOtpChange} />
                <Button type={'submit'} variant="solid" isLoading={isLoading} className={' w-full my-4'} size={'extraMedium'}>
                    {constants.continue}
                </Button>
            </form>
            <div className={`flex items-center gap-2  text-black-900 ${isModal ? 'mb-[182px]' : 'mb-[60px]'}`}>
                <p className="body4">{constants.didnotReceiveCode}</p>
                <>
                    {counter !== 0 && (
                        <p className="body4 text-gray-500 cursor-not-allowed">
                            {t(buttonConstant.resendCode)} <span className={'body4 text-brand-500'}>({counter})</span>
                        </p>
                    )}
                    {counter === 0 && (
                        <p
                            className="body4 cursor-pointer underline text-brand-500"
                            onClick={async () => {
                                await resendOtpCode();
                            }}
                        >
                            {t(buttonConstant.resendCode)}
                        </p>
                    )}
                </>
            </div>
        </>
    );
}

import React, { Dispatch, SetStateAction, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import Back from '@app/components/icons/back';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
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
    workspaceId?: string;
}

export default function OtpCodeComponent(props: OtpCodePropType) {
    const { t } = useTranslation();

    const { isModal } = props;

    const { closeModal } = useFullScreenModal();

    const workspace = useAppSelector((state) => state.workspace);

    const router = useRouter();

    const [otp, setOtp] = useState('');
    const [counter, setCounter] = useState(60);

    const [isError, setIsError] = useState(false);

    useEffect(() => {
        counter > 0 && setTimeout(() => setCounter(counter - 1), 1000);
    }, [counter]);

    const [postVerifyOtp, { isLoading }] = usePostVerifyOtpMutation();
    const [postSendOtp] = usePostSendOtpMutation();
    const [postSendOtpForCreator] = usePostSendOtpForCreatorMutation();

    const { fromProPlan } = router.query;

    const constants = {
        subHeading2: t(signInScreen.continueWIth),
        button: t(signInScreen.signUp),
        enterYourEmail: t(signInScreen.enterYourEmail),
        orSignInUsing: t(signInScreen.orSignInUsing),
        verificationTitle: t(signInScreen.verificationTitle),
        verificationDescription: t(signInScreen.verificationDescription),
        signInButton: t(signInScreen.signInButton),
        enterOtpCode: t(signInScreen.enterOtpCode),
        enterOtpCodePlaceholder: t(signInScreen.enterOtpCodePlaceholder),
        backButtonTitle: t(signInScreen.backButtonTitle),
        didnotReceiveCode: t(signInScreen.didNotReceiveCode),
        otpVerificationSuccess: t(formResponderLogin.verificationSuccessMessage),
        otpVerificationFailure: t(formResponderLogin.verificationFailureMessage)
    };

    const handleOtpChange = (e: any) => {
        setOtp(e.target.value);
        setIsError(false);
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
            setIsError(true);
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
                workspace_id: props.workspaceId ?? workspace.id
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
        const data = {
            body: req,
            params: { prospective_pro_user: fromProPlan }
        };
        const res = await postVerifyOtp(data);
        await handleResponseToast(res);
    };

    return (
        <div className="w-full">
            {props.isCreator && (
                <div className={`absolute flex items-center cursor-pointer gap-1 hover:text-brand ${isModal ? 'top-16' : ' top-24'}`} onClick={handleGoBackOnStepOne}>
                    <Back />
                    <p className={'hover:text-brand'}>{constants.backButtonTitle}</p>
                </div>
            )}
            <h3 className={`h4 mb-3 ${isModal ? 'mt-5' : ' mt-[44px]'}`}>{constants.verificationTitle}</h3>
            <h5 className="body4 !text-black-800">
                {constants.verificationDescription} <span className={'font-semibold text-pink'}>{props.email}</span>
            </h5>

            <form onSubmit={handleOtpPost} className={`w-full ${isModal && 'mt-10'}`}>
                <p className={`mb-[8px] text-black-900 text-md font-semibold ${!isModal && 'mt-10 '}`}>{constants.enterOtpCode}</p>
                <AppTextField isError={isError} placeholder={constants.enterOtpCodePlaceholder} value={otp} onChange={handleOtpChange} />
                {isError && <span className={'text-red-500 text-sm mt-1'}>Incorrect Code. Try Again!</span>}
                <AppButton className={'w-full mt-12'} type={'submit'} variant={ButtonVariant.Primary} size={ButtonSize.Medium} isLoading={isLoading}>
                    {constants.signInButton}
                </AppButton>
            </form>
            <div className={`flex items-center gap-2 mt-2 text-black-900 ${isModal ? 'mb-[84px]' : 'mb-16'}`}>
                <p className="body4">{constants.didnotReceiveCode}</p>
                <>
                    {counter !== 0 && (
                        <p className="body4 text-gray-500 cursor-not-allowed">
                            {t(buttonConstant.resendCode)} <span className={'body4 text-brand-500'}>({counter})</span>
                        </p>
                    )}
                    {counter === 0 && (
                        <p
                            className="body4 cursor-pointer underline !text-brand-500"
                            onClick={async () => {
                                await resendOtpCode();
                            }}
                        >
                            {t(buttonConstant.resendCode)}
                        </p>
                    )}
                </>
            </div>
        </div>
    );
}

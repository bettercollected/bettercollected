import React, { Dispatch, SetStateAction, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import Back from '@app/components/icons/back';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { usePostVerifyOtpMutation } from '@app/store/auth/api';

interface OtpCodePropType {
    stepCount: number;
    setStepCount: Dispatch<SetStateAction<number>>;
    email: string;
}

export default function OtpCodeComponent(props: OtpCodePropType) {
    const { t } = useTranslation();

    const [otp, setOtp] = useState('');
    const [counter, setCounter] = useState(60);
    const router = useRouter();

    const [postVerifyOtp, { isLoading }] = usePostVerifyOtpMutation();

    const constants = {
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

    const handleOtpChange = (e: any) => {
        setOtp(e.target.value);
    };

    const handleGoBackOnStepOne = () => {
        props.setStepCount(props.stepCount - 1);
    };

    const handleResponseToast = (res: any) => {
        if (!!res?.data) {
            toast(res.data.message, { type: 'success' });
            router.push('/login');
        } else {
            toast(!!res.error.data ? res.error.data : 'Failed to verify code', { type: 'error' });
        }
    };

    const handleOtpPost = async () => {
        if (!otp) return;
        const req = {
            email: props.email,
            otp_code: otp
        };
        const res = await postVerifyOtp(req);
        handleResponseToast(res);
    };

    return (
        <>
            <div className={'flex items-center mt-[48px] cursor-pointer gap-1 hover:text-brand'} onClick={handleGoBackOnStepOne}>
                <Back />
                <p className={'hover:text-brand'}>{constants.backButtonTitle}</p>
            </div>
            <h3 className="h3 mt-[44px] mb-[16px]">{constants.verificationTitle}</h3>
            <div className={'flex items-center sh2 text-brand-500'}>
                <p className="!text-black-700">{constants.subHeading2}</p>
                <div className={'!text-brand-500'}>{constants.button}</div>
            </div>

            <p className=" mb-[8px] mt-[44px] text-black-900">{constants.enterOtpCode}</p>
            <BetterInput placeholder={constants.enterOtpCode} value={otp} onChange={handleOtpChange} />
            <Button variant="solid" isLoading={isLoading} className={'w-full mt-[32px] mb-[40px]'} size={'large'} onClick={handleOtpPost}>
                {constants.continue}
            </Button>
            <div className={'flex items-center gap-2 mb-[60px] text-black-900'}>
                <p>{constants.didnotReceiveCode}</p>
                <>
                    {counter !== 0 && (
                        <p className="text-gray-500 cursor-not-allowed">
                            {t(buttonConstant.resendCode)} <span className={'text-brand-500'}>({counter})</span>
                        </p>
                    )}
                    {counter === 0 && (
                        <p
                            className="cursor-pointer"
                            onClick={() => {
                                setCounter(60);
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

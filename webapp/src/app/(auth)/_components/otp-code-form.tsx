'use client';

import React, { Dispatch, SetStateAction, useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'next/navigation';

import { Input } from '@app/shadcn/components/ui/input';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import { formResponderLogin } from '@app/constants/locales/form-responder-login';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { usePostSendOtpForCreatorMutation, usePostVerifyOtpMutation } from '@app/store/auth/api';

interface OtpCodeFormProps {
    email: string;
    isModal?: boolean;
    setEmail: Dispatch<SetStateAction<string>>;
}

export default function OtpCodeForm({ email, isModal, setEmail: setParentEmail }: OtpCodeFormProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const { closeModal } = useFullScreenModal();
    const [otp, setOtp] = useState('');
    const [counter, setCounter] = useState(60);
    const [isError, setIsError] = useState(false);

    useEffect(() => {
        if (counter > 0) {
            const timer = setTimeout(() => setCounter(counter - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [counter]);

    const [postVerifyOtp, { isLoading }] = usePostVerifyOtpMutation();
    const [postSendOtpForCreator] = usePostSendOtpForCreatorMutation();
    const searchParams = useSearchParams();
    const fromProPlan = searchParams?.get('fromProPlan');

    const constants = {
        otpVerificationSuccess: t(formResponderLogin.verificationSuccessMessage),
        otpVerificationFailure: t(formResponderLogin.verificationFailureMessage),
        enterOtpCode: t(signInScreen.enterOtpCode),
        enterOtpCodePlaceholder: t(signInScreen.enterOtpCodePlaceholder),
        didnotReceiveCode: t(signInScreen.didNotReceiveCode),
        signInButton: t(signInScreen.signInButton),
    };

    const handleOtpPost = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!otp) return;

        const data = {
            body: { email, otp_code: otp },
            params: { prospective_pro_user: fromProPlan! }
        };
        const res = await postVerifyOtp(data);

        if ('data' in res && !!res.data) {
            toast({ description: constants.otpVerificationSuccess });
            closeModal();
            if (typeof window !== 'undefined') {
                window.location.reload();
            }
        } else {
            setIsError(true);
            toast({ description: constants.otpVerificationFailure, variant: 'destructive' });
        }
    };

    const resendOtpCode = async () => {
        const res = await postSendOtpForCreator({ receiver_email: email });
        if ('data' in res && !!res.data) {
            setCounter(60);
        }
    };

    return (
        <form onSubmit={handleOtpPost} className="w-full">
            <p className="text-black-900 mb-3 text-base font-semibold">{constants.enterOtpCode}</p>
            <Input
                autoFocus
                placeholder={constants.enterOtpCodePlaceholder}
                value={otp}
                onChange={(e) => {
                    setOtp(e.target.value);
                    setIsError(false);
                }}
                className={isError ? 'border-red-500' : ''}
            />

            <div className="mt-8 flex items-center justify-between text-base">
                <p className="text-black-900 font-normal">{constants.didnotReceiveCode}</p>
                <div onClick={counter === 0 ? resendOtpCode : undefined} className={`font-semibold cursor-pointer ${counter === 0 ? 'text-brand-500 hover:text-brand-600' : 'text-black-400 cursor-not-allowed'}`}>
                    Resend {counter > 0 ? `(${counter}s)` : ''}
                </div>
            </div>

            <Button
                type="submit"
                variant="primary"
                isLoading={isLoading}
                className="mt-6 w-full"
                size="medium"
            >
                {constants.signInButton}
            </Button>
        </form>
    );
}

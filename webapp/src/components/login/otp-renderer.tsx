import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import { buttonConstant } from '@app/constants/locales/button';
import { otpRenderer } from '@app/constants/locales/otp-renderer';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useLazyGetStatusQuery, usePostSendOtpMutation, usePostVerifyOtpMutation } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

export default function OtpRenderer({ email, isCustomDomain }: any) {
    const { closeModal } = useModal();
    const workspace = useAppSelector((state) => state.workspace);
    const [counter, setCounter] = useState(60);
    const [otp, setOtp] = useState('');
    const { t } = useTranslation();
    const [postSendOtp, response] = usePostSendOtpMutation();

    const [postVerifyOtp, result] = usePostVerifyOtpMutation();
    const { isLoading } = result;

    const [trigger] = useLazyGetStatusQuery();

    const emailRequest: any = { receiver_email: email };

    useEffect(() => {
        counter > 0 && setTimeout(() => setCounter(counter - 1), 1000);
    }, [counter]);

    const handleVerifyButtonClick = async (e: any) => {
        e.preventDefault();
        if (otp.length === 0) {
            toast.error(t(toastMessage.otpFieldNullError).toString(), { toastId: ToastId.ERROR_TOAST });
            return;
        }
        const response = { email: email, otp_code: otp };
        await postVerifyOtp(response)
            .unwrap()
            .then(async () => await trigger())
            .then(() => closeModal())
            .catch((err) => toast.error(err, { toastId: ToastId.ERROR_TOAST }));
    };

    const handleChange = (e: any) => {
        setOtp(e.target.value.toUpperCase());
    };

    return (
        <form className="relative flex flex-col items-center justify-between p-10">
            <div>
                <h2 className="sh1 text-center">{t(otpRenderer.title)}</h2>
                <p className="!text-black-600 body4 text-center mt-4 leading-none">
                    {t(otpRenderer.subtitle)} <br />
                    <span className="text-brand-500 italic">{email}</span>
                </p>
            </div>
            <BetterInput data-testid="otp-input" className="mt-6" spellCheck={false} value={otp} type="text" placeholder={'Enter the OTP code'} onChange={handleChange} />
            <div className="w-full">
                <Button data-testid="verify-button" isLoading={isLoading} disabled={!otp} onClick={handleVerifyButtonClick} size="medium" className="w-full">
                    {t(buttonConstant.verify)}
                </Button>
                <div className={'text-md align flex mt-4 items-center justify-center text-black-900'}>
                    {counter !== 0 && (
                        <div className="text-gray-500 cursor-not-allowed border-none">
                            {t(buttonConstant.resendCode)} ({counter})
                        </div>
                    )}
                    {counter === 0 && (
                        <div
                            className="cursor-pointer"
                            onClick={() => {
                                emailRequest.workspace_id = workspace.id;
                                postSendOtp(emailRequest);
                                setCounter(60);
                            }}
                        >
                            {t(buttonConstant.resendCode)}
                        </div>
                    )}
                </div>
            </div>
        </form>
    );
}

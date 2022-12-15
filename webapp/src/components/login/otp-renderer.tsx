import { useEffect, useState } from 'react';

import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import { useLazyGetStatusQuery, usePostSendOtpMutation, usePostVerifyOtpMutation } from '@app/store/auth/api';

export default function OtpRenderer({ email }: any) {
    const { closeModal } = useModal();

    const [counter, setCounter] = useState(0);
    const [otp, setOtp] = useState('');
    const [postSendOtp, response] = usePostSendOtpMutation();

    const [postVerifyOtp, result] = usePostVerifyOtpMutation();
    const { isLoading } = result;

    const [trigger] = useLazyGetStatusQuery();

    const emailRequest = { receiver_email: email };

    useEffect(() => {
        counter > 0 && setTimeout(() => setCounter(counter - 1), 1000);
    }, [counter]);

    const handleVerifyButtonClick = async (e: any) => {
        e.preventDefault();
        if (otp.length === 0) {
            toast.error('OTP field cannot be empty!');
            return;
        }
        const response = { email: email, otp_code: otp };
        await postVerifyOtp(response)
            .unwrap()
            .then(async () => await trigger('status'))
            .then(() => closeModal())
            // .then(() => toast.info('Login successful'))
            .catch((err) => toast.error(err));
    };

    const ResendButtonRenderer = () => {
        return (
            <div className={'text-md align flex mt-4 cursor-pointer  items-center justify-center text-primary hover:text-blue-500 hover:underline'}>
                {counter !== 0 && <div className="text-gray-500 underline-offset-0 border-none">Resend code ({counter})</div>}
                {counter === 0 && (
                    <div
                        className="hover:underline-offset-1"
                        onClick={() => {
                            postSendOtp(emailRequest);
                            setCounter(60);
                        }}
                    >
                        Resend code
                    </div>
                )}
            </div>
        );
    };

    const HeaderRenderer = () => {
        return (
            <>
                <div className={'font-semibold text-darkGrey rounded-md text-md'}>Enter OTP code</div>

                <p className={'text-sm text-gray-500 md:text-base'}> We have just send a verification code to</p>
                <p className="text-darkGrey font-semibold mb-2">{email}</p>
            </>
        );
    };

    return (
        <form className={'flex flex-col text-center'}>
            <HeaderRenderer />
            <input className={`border-solid mb-4 h-[40px] text-gray-900 text-sm rounded-lg w-full p-2.5`} value={otp} type="text" placeholder={'Enter the OTP code'} onChange={(e: any) => setOtp(e.target.value.toUpperCase())} />
            <Button isLoading={isLoading} onClick={handleVerifyButtonClick} className="w-full">
                Verify
            </Button>
            <ResendButtonRenderer />
        </form>
    );
}

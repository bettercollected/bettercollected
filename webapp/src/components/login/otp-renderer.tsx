import { useEffect, useState } from 'react';

import { toast } from 'react-toastify';

import { usePostAuthEmailMutation, usePostVerifyOtpMutation } from '@app/store/otp/api';

import { useModal } from '../modal-views/context';
import Button from '../ui/button/button';

export default function OtpRenderer({ email }: any) {
    const { closeModal } = useModal();

    const [counter, setCounter] = useState(0);
    const [otp, setOtp] = useState('');
    const [postAuthEmail, response] = usePostAuthEmailMutation();

    const [postVerifyOtp, result] = usePostVerifyOtpMutation();

    const { isLoading } = result;

    const emailRequest = { receiver_email: email };

    useEffect(() => {
        counter > 0 && setTimeout(() => setCounter(counter - 1), 1000);
    }, [counter]);

    const handleVerifyButtonClick = async (e: any) => {
        e.preventDefault();
        if (otp.length === 0) {
            toast.error('Otp field cannot be empty!');
            return;
        }
        const response = { email: email, otp_code: otp };
        const result = await postVerifyOtp(response).unwrap();
        if (result.status_code === 200) {
            toast.info(result.detail);
            closeModal();
        } else {
            toast.error(result.detail);
        }
    };

    const ResendButtonRenderer = () => {
        return (
            <div className={'text-md align flex mt-4 cursor-pointer  items-center justify-center text-primary hover:text-blue-500 hover:underline'}>
                {counter !== 0 && <div className="text-gray-500 underline-offset-0 border-none">Resend code ({counter})</div>}

                {counter === 0 && (
                    <div
                        className="hover:underline-offset-1"
                        onClick={() => {
                            postAuthEmail(emailRequest);
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
                <div className={'font-semibold text-darkGrey rounded-md text-xl'}>Enter OTP code to Verify</div>

                <div className={'text-sm mb-2 text-gray-400 md:text-base'}>
                    {' '}
                    We have just send a verification code to <span className="text-black font-bold">{email}</span>
                    <br />
                </div>
            </>
        );
    };

    return (
        <form className={' flex flex-col text-center'}>
            <HeaderRenderer />
            <input className={`border-solid mb-4 h-[40px] text-gray-900 text-sm rounded-lg w-full p-2.5`} value={otp} type="text" placeholder={'Enter the OTP code'} onChange={(e: any) => setOtp(e.target.value)} />
            <Button isLoading={isLoading} onClick={handleVerifyButtonClick} className="w-full">
                Verify
            </Button>
            <ResendButtonRenderer />
        </form>
    );
}

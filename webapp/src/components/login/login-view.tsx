import { useRef, useState } from 'react';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Image from '@app/components/ui/image';
import { usePostSendOtpMutation } from '@app/store/auth/api';

import OtpRenderer from './otp-renderer';
import SendCode from './sendcode-renderer';

export default function LoginView() {
    const { closeModal } = useModal();
    const [postSendOtp, result] = usePostSendOtpMutation();
    const { isLoading, isSuccess } = result;

    const [email, setEmail] = useState('');

    function updateEmail(email: string) {
        setEmail(email);
    }

    const ref = useRef<HTMLDivElement>(null);

    return (
        <div ref={ref} className="relative m-auto w-full items-start justify-between rounded-lg bg-white scale-110">
            <div className="relative flex flex-col items-center gap-8 justify-between p-10">
                <Image src="/otp.svg" width="150px" height="150px" alt="OTP Image" />
                {isSuccess ? <OtpRenderer email={email} /> : <SendCode updateEmail={updateEmail} isLoading={isLoading} postSendOtp={postSendOtp} />}
            </div>
            <Close onClick={() => closeModal()} className="cursor-pointer absolute top-3 right-3 h-auto w-3 text-gray-600 hover:text-black dark:text-white" />
        </div>
    );
}

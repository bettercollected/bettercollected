import { useRef, useState } from 'react';

import 'react-toastify/dist/ReactToastify.css';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Image from '@app/components/ui/image';
import { usePostSendOtpMutation } from '@app/store/auth/api';

import OtpRenderer from './otp-renderer';
import SendCode from './sendcode-renderer';

export default function LoginView({ ...props }) {
    function EmailAndOTPUiSwitcher() {
        const [postSendOtp, result] = usePostSendOtpMutation();
        const { isLoading, isSuccess } = result;

        const [email, setEmail] = useState('');

        function updateEmail(email: string) {
            setEmail(email);
        }

        return isSuccess ? <OtpRenderer email={email} /> : <SendCode updateEmail={updateEmail} isLoading={isLoading} postSendOtp={postSendOtp} />;
    }

    function ImageRenderer() {
        return (
            <div>
                <Image src="/otp.svg" width="150px" height="150px" alt="OTP Image" />
            </div>
        );
    }

    function LoginContainer() {
        const { closeModal } = useModal();

        const ref = useRef<HTMLDivElement>(null);

        return (
            <div ref={ref} className=" relative m-auto max-w-[500px] items-start justify-between rounded-lg bg-white lg:scale-150">
                <div className=" relative flex flex-col  items-center gap-8 justify-between p-10">
                    <ImageRenderer />
                    <EmailAndOTPUiSwitcher />
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        );
    }

    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <LoginContainer />
        </div>
    );
}

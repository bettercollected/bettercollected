import { useRef, useState } from 'react';

import { Close } from '@app/components/icons/close';
import OtpRenderer from '@app/components/login/otp-renderer';
import SendCode from '@app/components/login/sendcode-renderer';
import { useModal } from '@app/components/modal-views/context';
import { usePostSendOtpMutation } from '@app/store/auth/api';

export default function LoginView(props: any) {
    const { closeModal } = useModal();
    const { isCustomDomain } = props;
    const [postSendOtp, { isLoading, isSuccess }] = usePostSendOtpMutation();

    const [email, setEmail] = useState('');

    function updateEmail(email: string) {
        setEmail(email);
    }

    const ref = useRef<HTMLDivElement>(null);

    return (
        <div ref={ref} className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <div className="rounded-[4px] relative m-auto max-w-[500px] items-start justify-between bg-white">
                {isSuccess ? <OtpRenderer email={email} isCustomDomain={isCustomDomain} /> : <SendCode updateEmail={updateEmail} isCustomDomain={isCustomDomain} isLoading={isLoading} postSendOtp={postSendOtp} />}
            </div>
            <Close onClick={() => closeModal()} className="cursor-pointer absolute top-3 right-3 h-auto w-3 text-gray-600 hover:text-black dark:text-white" />
        </div>
    );
}

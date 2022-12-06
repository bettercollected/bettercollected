import { useRef, useState } from 'react';

import 'react-toastify/dist/ReactToastify.css';

import { usePostAuthEmailMutation } from '@app/store/otp/api';

import { Close } from '../icons/close';
import { useModal } from '../modal-views/context';
import OtpRenderer from './otp-renderer';
import SendCode from './sendcode-renderer';

export default function LoginView({ ...props }) {
    function EmailAndOTPUiSwitcher() {
        const [postAuthEmail, result] = usePostAuthEmailMutation();
        const { isLoading, isSuccess } = result;

        const [email, setEmail] = useState('');

        function updateEmail(email: string) {
            setEmail(email);
        }

        return isSuccess ? <OtpRenderer email={email} /> : <SendCode updateEmail={updateEmail} isLoading={isLoading} postAuthEmail={postAuthEmail} />;
    }

    function ImageRenderer() {
        return (
            <div>
                <img src={'/otp.svg'} width="150px" height="150px" />
            </div>
        );
    }

    function LoginContainer() {
        const { closeModal } = useModal();

        const ref = useRef<HTMLDivElement>(null);

        return (
            <div ref={ref} className=" relative m-auto max-w-[500px] items-start justify-between rounded-lg bg-white lg:scale-150">
                <form className=" relative flex flex-col  items-center gap-8 justify-between p-10">
                    <ImageRenderer />
                    <EmailAndOTPUiSwitcher />
                </form>
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

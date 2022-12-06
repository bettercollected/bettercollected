import { useState } from 'react';

import 'react-toastify/dist/ReactToastify.css';

import { usePostAuthEmailMutation } from '@app/store/otp/api';

import { useModal } from '../modal-views/context';
import OtpRenderer from './otp-renderer';
import SendCode from './sendcode-renderer';

export default function LoginView({ ...props }) {
    const { closeModal } = useModal();

    function EmailAndOTPUiSwitcher() {
        const [postAuthEmail, result] = usePostAuthEmailMutation();
        const { isLoading, isSuccess } = result;

        const [email, setEmail] = useState('');

        function updateEmail(email: string) {
            setEmail(email);
        }

        if (isSuccess) {
            return <OtpRenderer email={email} />;
        } else {
            return <SendCode updateEmail={updateEmail} isLoading={isLoading} postAuthEmail={postAuthEmail} />;
        }
    }

    function ImageRenderer() {
        return (
            <div>
                <img src={'/otp.svg'} width="150px" height="150px" />
            </div>
        );
    }

    function LoginContainer() {
        return (
            <div className=" m-auto max-w-[500px] items-start justify-between rounded-lg bg-white lg:scale-150">
                <div className="flex flex-col  items-center gap-8 justify-between p-10">
                    <ImageRenderer />
                    {/* <OtpRenderer /> */}
                    <EmailAndOTPUiSwitcher />
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                    X
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

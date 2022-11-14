import { useEffect, useState } from 'react';

import styled from '@emotion/styled';
import TextField from '@mui/material/TextField';

import Button from '@app/components/ui/button';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { usePostAuthEmailMutation, usePostVerifyOtpMutation } from '@app/store/otp/api';

import { useModal } from './modal-views/context';
import FormInput from './ui/FormInput';

const StyledTextField = styled.div`
    .MuiFormControl-root {
        background: white;
    }
`;

export default function LoginView({ ...props }) {
    function OtpRenderer({ email }: any) {
        const [showCountDown, setShowCountDown] = useState(true);
        const [counter, setCounter] = useState(60);
        const [otp, setOtp] = useState('');

        const [postVerifyOtp, result] = usePostVerifyOtpMutation();

        const { isLoading } = result;

        useEffect(() => {
            counter > 0 && setTimeout(() => setCounter(counter - 1), 1000);
        }, [counter]);

        const Countdown = () => <>{counter}</>;

        const handleClick = (e: any) => {
            e.preventDefault();
            const response = { email: email, otp_code: otp };
            postVerifyOtp(response);
        };

        return (
            <form className={'mr-10 flex flex-col space-y-sm'}>
                <div className={'font-semibold text-darkGrey rounded-md text-xl'}>Enter Verification code</div>

                <div className={' text-sm text-gray-600 md:text-base'}>
                    {' '}
                    We have just send the verification code to {email}
                    <br />
                </div>

                <TextField placeholder="Enter OTP code" className="border-none  p-1 outline-none focus:bg-white" onChange={(e) => setOtp(e.target.value)} value={otp} />

                <Button isLoading={isLoading} onClick={handleClick}>
                    Verify
                </Button>
                <div className={'text-md align flex cursor-pointer  items-center justify-center text-primary hover:text-blue-500 hover:underline'}>
                    <Button disabled={!showCountDown} className="hover:underline-offset-1">
                        Resend code {showCountDown && <Countdown />}
                    </Button>
                </div>
            </form>
        );
    }

    function SendCode({ updateEmail, isLoading, postAuthEmail }: any) {
        const [emailInput, setEmailInput] = useState('');

        const handleClick = () => {
            const email = { receiver_email: emailInput };
            updateEmail(emailInput);
            postAuthEmail(email);
        };

        return (
            <div className="flex flex-col justify-center">
                {/* <TextField className="h-[35px] w-full border-solid border-[#eaeaea] mb-5" onChange={(e) => setEmailInput(e.target.value)} placeholder="Enter your email" /> */}
                <FormInput value={emailInput} placeholder={'Enter your email'} onChange={(e: any) => setEmailInput(e.target.value)} />
                <Button isLoading={isLoading} variant="solid" className="mt-2 mb-0" onClick={handleClick}>
                    Get in
                </Button>
            </div>
        );
    }

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
        const screenSize = useBreakpoint();

        switch (screenSize) {
            case 'sm':
                return <></>;
            case 'xs':
                return <></>;
            default:
                return (
                    <div>
                        <img src={'/otp.svg'} height="200px" width={'200px'} />
                    </div>
                );
        }
    }

    function LoginContainer() {
        const { closeModal } = useModal();
        return (
            <div className=" m-auto max-w-[500px] items-start justify-between rounded-lg bg-white lg:scale-150">
                <div className="flex flex-row items-center gap-8 justify-between p-10">
                    <EmailAndOTPUiSwitcher />
                    <ImageRenderer />
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

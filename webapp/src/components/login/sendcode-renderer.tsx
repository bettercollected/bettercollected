import { useState } from 'react';

import BetterInput from '@app/components/Common/input';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { useAppSelector } from '@app/store/hooks';

export default function SendCode({ updateEmail, isLoading, postSendOtp, isCustomDomain }: any) {
    const workspace = useAppSelector((state) => state.workspace);

    const [emailInput, setEmailInput] = useState('');

    const handleClick = (e: any) => {
        e.preventDefault();
        const email: any = { receiver_email: emailInput };
        email.workspace_id = workspace.id;
        updateEmail(emailInput);
        postSendOtp(email);
    };

    const handleChangeOnInput = (e: any) => {
        setEmailInput(e.target.value.toLowerCase());
    };

    return (
        <form onSubmit={handleClick} className="relative flex flex-col items-center justify-between p-10">
            <div>
                <h2 className="sh1 text-center">Enter your email</h2>
                <p className="!text-black-600 mt-2 body4 text-center leading-none">An OTP code will be sent to your email account</p>
            </div>
            <BetterInput type="email" className="mt-8" value={emailInput} placeholder={'Enter your email'} onChange={handleChangeOnInput} />
            <div className="w-full px-2">
                <Button data-testid="get-in-button" size="medium" type="submit" isLoading={isLoading} variant="solid" className={`w-full`} onClick={handleClick}>
                    Get In
                </Button>
                <div className="flex py-5 items-center justify-center">
                    <div className="border-t w-5 border-gray-200"></div>
                    <span className="flex-shrink text-xs mx-4 text-gray-400">or</span>
                    <div className="border-t w-5 border-gray-200"></div>
                </div>
                <ConnectWithProviderButton url={`${environments.API_ENDPOINT_HOST}/auth/google/basic`} text="Sign in with Google" creator={false} />
            </div>
        </form>
    );
}

import { useState } from 'react';

import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import FormInput from '@app/components/ui/FormInput';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { useAppSelector } from '@app/store/hooks';

export default function SendCode({ updateEmail, isLoading, postSendOtp, isCustomDomain }: any) {
    const workspace = useAppSelector((state) => state.workspace);

    const [emailInput, setEmailInput] = useState('');

    const [emailValid, setEmailValid] = useState(false);

    const handleClick = (e: any) => {
        e.preventDefault();
        const email: any = { receiver_email: emailInput };
        if (isCustomDomain) {
            email.workspace_id = workspace.id;
        }
        updateEmail(emailInput);
        postSendOtp(email);
    };

    const handleValidation = (isValid: boolean) => {
        setEmailValid(isValid);
    };

    const handleChangeOnInput = (e: any) => {
        setEmailInput(e.target.value.toLowerCase());
    };

    return (
        <form onSubmit={handleClick} className="flex flex-col justify-center">
            <h2 className="text-lg font-bold text-center">Enter your email</h2>
            <p className="text-gray-400 text-xs mb-4">An OTP code will be sent to your email account</p>
            <FormInput inputFieldType="email" value={emailInput} placeholder={'Enter your email'} onChange={handleChangeOnInput} handleValidation={handleValidation} />
            <Button data-testid="get-in-button" type="submit" disabled={!emailValid} isLoading={isLoading} variant="solid" className={`mt-2 w-60 mb-0 mx-auto !rounded-[1px] !h-[50px]`} onClick={handleClick}>
                Get In
            </Button>
            <div className="flex py-5 items-center justify-center">
                <div className="border-t w-5 border-gray-200"></div>
                <span className="flex-shrink text-xs mx-4 text-gray-400">or</span>
                <div className="border-t w-5 border-gray-200"></div>
            </div>
            <ConnectWithProviderButton url={`${environments.API_ENDPOINT_HOST}/auth/google/basic`} text="Sign in with Google" creator />
        </form>
    );
}

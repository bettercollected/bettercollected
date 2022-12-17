import { useState } from 'react';

import ConnectWithGoogleButton from '@app/components/login/login-with-google-button';
import FormInput from '@app/components/ui/FormInput';
import Button from '@app/components/ui/button';

export default function SendCode({ updateEmail, isLoading, postSendOtp }: any) {
    const [emailInput, setEmailInput] = useState('');

    const [emailValid, setEmailValid] = useState(false);

    const handleClick = (e: any) => {
        e.preventDefault();
        const email = { receiver_email: emailInput };
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
            <h2 className="text-lg font-bold text-center">Enter your Gmail</h2>
            <p className="text-gray-400 text-xs mb-4">An OTP code will be sent to your gmail account</p>
            <FormInput inputFieldType="email" value={emailInput} placeholder={'Enter your email'} onChange={handleChangeOnInput} handleValidation={handleValidation} />
            <Button type="submit" disabled={!emailValid} isLoading={isLoading} variant="solid" className={`mt-2 w-full mb-0 !rounded-lg !h-10`} onClick={handleClick}>
                Get in
            </Button>
            <div className="flex py-5 items-center justify-center">
                <div className="border-t w-5 border-gray-200"></div>
                <span className="flex-shrink text-xs mx-4 text-gray-400">or</span>
                <div className="border-t w-5 border-gray-200"></div>
            </div>
            <ConnectWithGoogleButton className="!w-full !max-w-full" text="Continue with google" />
        </form>
    );
}

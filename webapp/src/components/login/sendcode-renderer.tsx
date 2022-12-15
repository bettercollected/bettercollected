import { useState } from 'react';

import { useRouter } from 'next/router';

import { Google } from '@app/components/icons/brands/google';
import environments from '@app/configs/environments';

import FormInput from '../ui/FormInput';
import Button from '../ui/button';

export default function SendCode({ updateEmail, isLoading, postSendOtp }: any) {
    const [emailInput, setEmailInput] = useState('');

    const [emailValid, setEmailValid] = useState(false);

    const router = useRouter();
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
        setEmailInput(e.target.value);
    };

    const handleGoogleOauthLogin = (e: any) => {
        router.push(`${environments.API_ENDPOINT_HOST}/auth/google/basicAuth`);
    };
    return (
        <form onSubmit={handleClick} className="flex flex-col justify-center">
            <h2 className="text-lg font-bold text-center">Enter your Gmail</h2>
            <p className="text-gray-400 text-sm mb-4">An OTP code will be sent to your gmail account</p>
            <FormInput inputFieldType="email" value={emailInput} placeholder={'Enter your email'} onChange={handleChangeOnInput} handleValidation={handleValidation} />
            <Button type="submit" disabled={!emailValid} isLoading={isLoading} variant="solid" className={`mt-2 w-full mb-0`} onClick={handleClick}>
                Get in
            </Button>
            <div className="flex py-5 items-center justify-center">
                <div className="border-t w-5 border-gray-400"></div>
                <span className="flex-shrink mx-4 text-gray-400">or</span>
                <div className="border-t w-5 border-gray-400"></div>
            </div>
            <button type="submit" className="bg-[#1a73e8] max-w-[250px] mx-auto flex w-full items-center rounded-2xl p-[2px]" onClick={handleGoogleOauthLogin}>
                <div className=" rounded-full bg-white p-2">
                    <Google />
                </div>
                <div className="flex items-center w-full justify-center font-bold text-white text-[10px]">Continue with google</div>
            </button>
        </form>
    );
}

import { useState } from 'react';

import FormInput from '../ui/FormInput';
import Button from '../ui/button';

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
        setEmailInput(e.target.value);
    };

    return (
        <div className="flex flex-col justify-center">
            <form onSubmit={handleClick}>
                <h2 className="text-lg font-bold text-center">Enter your Gmail</h2>
                <p className="text-gray-400 text-sm mb-4">An OTP code will be sent to your gmail account</p>
                <FormInput inputFieldType="email" value={emailInput} placeholder={'Enter your email'} onChange={handleChangeOnInput} handleValidation={handleValidation} />
                <Button type="submit" disabled={!emailValid} isLoading={isLoading} variant="solid" className={`mt-2 w-full mb-0`} onClick={handleClick}>
                    Get in
                </Button>
            </form>
        </div>
    );
}

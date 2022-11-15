import { useState } from 'react';

import FormInput from '../ui/FormInput';
import Button from '../ui/button';

export default function SendCode({ updateEmail, isLoading, postAuthEmail }: any) {
    const [emailInput, setEmailInput] = useState('');

    const [emailValid, setEmailValid] = useState(false);

    const handleClick = () => {
        const email = { receiver_email: emailInput };
        updateEmail(emailInput);
        postAuthEmail(email);
    };

    const handleValidation = (isValid: boolean) => {
        setEmailValid(isValid);
    };

    const handleChangeOnInput = (e: any) => {
        console.log(e.target.value);

        setEmailInput(e.target.value);
    };

    return (
        <div className="flex flex-col justify-center">
            <h2 className="text-lg font-bold text-center">Enter your Gmail</h2>
            <p className="text-gray-400 text-sm mb-4">An OTP code will be sent to your gmail account</p>
            <FormInput inputFieldType="email" value={emailInput} placeholder={'Enter your email'} onChange={handleChangeOnInput} handleValidation={handleValidation} />
            <Button disabled={!emailValid} isLoading={isLoading} variant="solid" className={`mt-2 w-full mb-0`} onClick={handleClick}>
                Get in
            </Button>
        </div>
    );
}

import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import BetterInput from '@app/components/Common/input';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { buttons, localesDefault, otpRenderer } from '@app/constants/locales';
import { useAppSelector } from '@app/store/hooks';

import FormInput from '../ui/FormInput';

export default function SendCode({ updateEmail, isLoading, postSendOtp, isCustomDomain }: any) {
    const workspace = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();
    const [emailInput, setEmailInput] = useState('');

    const [emailValid, setEmailValid] = useState(false);

    const handleClick = (e: any) => {
        e.preventDefault();
        const email: any = { receiver_email: emailInput };
        email.workspace_id = workspace.id;
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
        <form onSubmit={handleClick} className="relative flex flex-col items-center gap-8 justify-between p-10">
            <div>
                <h2 className="sh1 text-center">{t(localesDefault.enterEmail)}</h2>
                <p className="!text-black-600 mt-2 body4 text-center leading-none">{t(otpRenderer.sendMessage)}</p>
            </div>
            <FormInput inputFieldType="email" value={emailInput} placeholder={t(localesDefault.enterEmail)} onChange={handleChangeOnInput} handleValidation={handleValidation} />
            {/* <BetterInput type="email" className="mt-8" value={emailInput} placeholder={'Enter your email'} onChange={handleChangeOnInput} /> */}
            <div>
                <Button data-testid="get-in-button" type="submit" disabled={!emailValid} isLoading={isLoading} variant="solid" className={`w-60 mx-auto !rounded-[1px] !h-[50px]`} onClick={handleClick}>
                    {t(buttons.getIn)}
                </Button>
                <div className="flex py-5 items-center justify-center">
                    <div className="border-t w-5 border-gray-200"></div>
                    <span className="flex-shrink text-xs mx-4 text-gray-400">{t(localesDefault.or)}</span>
                    <div className="border-t w-5 border-gray-200"></div>
                </div>
                <ConnectWithProviderButton url={`${environments.API_ENDPOINT_HOST}/auth/google/basic`} text="Sign in with Google" creator={false} />
            </div>
        </form>
    );
}

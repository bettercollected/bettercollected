import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import ConnectWithProviderButton from '@app/Components/Login/login-with-google-button';
import FormInput from '@app/Components/ui/FormInput';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { otpRenderer } from '@app/constants/locales/otp-renderer';
import { IntegrationFormProviders } from '@app/models/dtos/provider';
import { useAppSelector } from '@app/store/hooks';
import { capitalize } from '@app/utils/stringUtils';


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
        <form onSubmit={handleClick} className="relative flex flex-col items-center justify-between gap-8 p-10">
            <div>
                <h2 className="sh1 text-center">{t(localesCommon.enterEmail)}</h2>
                <p className="!text-black-600 body4 mt-2 text-center leading-none">{t(otpRenderer.sendMessage)}</p>
            </div>
            <FormInput inputFieldType="email" value={emailInput} placeholder={t(localesCommon.enterEmail)} onChange={handleChangeOnInput} handleValidation={handleValidation} />
            {/* <BetterInput type="email" className="mt-8" value={emailInput} placeholder={'Enter your email'} onChange={handleChangeOnInput} /> */}
            <div>
                <AppButton data-testid="get-in-button" type="submit" disabled={!emailValid} isLoading={isLoading} className={`mx-auto !h-[50px] w-60 !rounded-[1px]`} onClick={handleClick}>
                    {t(buttonConstant.getIn)}
                </AppButton>
                <div className="flex items-center justify-center py-5">
                    <div className="w-5 border-t border-gray-200"></div>
                    <span className="mx-4 flex-shrink text-xs text-gray-400">{t(localesCommon.or)}</span>
                    <div className="w-5 border-t border-gray-200"></div>
                </div>
                <FormProviderContext.Consumer>
                    {(formProviders: Array<IntegrationFormProviders>) => (
                        <div className="flex flex-col gap-5">
                            {formProviders.map((provider: IntegrationFormProviders) => (
                                <ConnectWithProviderButton
                                    key={provider.providerName}
                                    type={provider.providerName === 'typeform' ? 'typeform' : 'dark'}
                                    url={`${environments.API_ENDPOINT_HOST}/auth/${provider.providerName}/basic`}
                                    text={`Sign in with ${capitalize(provider.providerName)}`}
                                    creator={false}
                                />
                            ))}
                        </div>
                    )}
                </FormProviderContext.Consumer>
                {/* <ConnectWithProviderButton url={`${environments.API_ENDPOINT_HOST}/auth/google/basic`} text="Sign in with Google" creator={false} /> */}
            </div>
        </form>
    );
}
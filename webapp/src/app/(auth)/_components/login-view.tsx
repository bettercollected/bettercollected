'use client';

import Image from "next/legacy/image";
import { useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import Logo from '@app/components/ui/logo';
import { localesCommon } from '@app/constants/locales/common';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import TopNavLayout from '@app/layouts/top-navbar-layout';

import ImageSignInPreview from '@app/assets/images/sign-in-image.png';
import ImageSignInVerification from '@app/assets/images/sign-in-verification.png';
import ImageSignUpPreview from '@app/assets/images/sign-up-image.png';
import ImageSignUpValidation from '@app/assets/images/sign-up-verification.png';

import OtpCodeForm from './otp-code-form';
import OtpEmailForm from './otp-email-form';

export default function LoginView() {
    const { t } = useTranslation();
    const isSignup = useSearchParams()?.get('isSignup') === 'true';
    const [email, setEmail] = useState('');

    const constants = {
        signInEmailTitle: t(signInScreen.features.title),
        signInEmailDescription: t(signInScreen.features.description),
        signInCodeTitle: t(signInScreen.features.otp_title),
        signInCodeDescription: t(signInScreen.features.otp_description),
        signUpLogoSubTitle: t(signUpScreen.logoDescription),
        signUpAgreementDescription: t(signUpScreen.signUpAgreementDescription),
        signUpEmailTitle: t(signUpScreen.features.title),
        signUpEmailDescription: t(signUpScreen.features.description),
        signUpCodeTitle: t(signUpScreen.features.otp_title),
        signUpCodeSubTitle: t(signUpScreen.features.otp_subtitle),
        signUpCodeDescription: t(signUpScreen.features.otp_description),
    };

    return (
        <TopNavLayout className="min-h-screen !mt-0 !p-0">
            <div className="h-full w-full flex flex-col lg:flex-row">
                <div className="bg-sign-in bg-no-repeat bg-cover relative min-h-fit sm:min-h-screen order-2 lg:order-1 overflow-hidden w-full lg:w-[50%] flex flex-col justify-start">
                    {email ? (
                        <PreviewContent
                            title={isSignup ? constants.signUpCodeTitle : constants.signInCodeTitle}
                            description={isSignup ? constants.signUpCodeDescription : constants.signInCodeDescription}
                            subtitle={isSignup ? constants.signUpCodeSubTitle : undefined}
                            image={isSignup ? ImageSignUpValidation : ImageSignInVerification}
                        />
                    ) : (
                        <PreviewContent
                            title={isSignup ? constants.signUpEmailTitle : constants.signInEmailTitle}
                            description={isSignup ? constants.signUpEmailDescription : constants.signInEmailDescription}
                            image={isSignup ? ImageSignUpPreview : ImageSignInPreview}
                        />
                    )}
                </div>
                <div className="relative flex flex-col order-1 lg:order-2 items-start justify-between px-8 py-7 lg:py-8 xl:pl-[90px] xl:pr-28 min-h-fit sm:min-h-screen w-full lg:max-w-[50%]">
                    <div className="mb-20 lg:mb-0">
                        <Logo isLink={false} />
                        <h1 className="body4 !text-black-800 mt-2">{constants.signUpLogoSubTitle}</h1>
                    </div>

                    <div className="w-full">
                        {!email ? (
                            <OtpEmailForm setEmail={setEmail} isSignup={isSignup} />
                        ) : (
                            <OtpCodeForm email={email} setEmail={setEmail} />
                        )}
                    </div>

                    <TermsAndCondition isSignup={isSignup} constants={constants} />
                </div>
            </div>
        </TopNavLayout>
    );
}

const PreviewContent = ({ title, description, subtitle, image }: { title: string, description: string, subtitle?: string, image: any }) => (
    <>
        <div className="flex flex-col gap-4 items-center justify-center px-8 mt-28 mb-8 lg:max-h-[300px] text-center">
            {subtitle && <h1 className="text-base font-semibold text-white mb-1">{subtitle}</h1>}
            <h1 className="text-base md:text-[32px] leading-normal text-white font-semibold sm:w-[500px]">{title}</h1>
            <span className="font-normal text-black-200 text-xs md:text-base sm:w-[400px]">{description}</span>
        </div>
        <div className="flex w-full justify-center lg:px-[60px] px-8 ">
            <div className="lg:h-[400px] h-[300px] w-fit">
                <Image src={image} alt="BetterCollected" objectFit="contain" />
            </div>
        </div>
    </>
);

const TermsAndCondition = ({ isSignup, constants }: { isSignup: boolean, constants: any }) => {
    const { t } = useTranslation();
    return (
        <div className="body4 mt-24 lg:mt-0">
            {t(isSignup ? constants.signUpAgreementDescription : signInScreen.signinAgreementDescription)}
            <a href="https://bettercollected.com/terms-of-service" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline text-brand-500 hover:text-brand-600">
                {t(localesCommon.termsOfServices.title)}
            </a>
            {t(localesCommon.and)}
            <a href="https://bettercollected.com/privacy-policy" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline text-brand-500 hover:text-brand-600">
                {t(localesCommon.privacyPolicy.title)}
            </a>
            .
        </div>
    );
};

import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';
import { useRouter } from 'next/router';

import OtpCodeComponent from '@Components/Login/otp-code-component';
import OtpEmailInput from '@Components/Login/otp-email-input';
import cn from 'classnames';

import ImageSignInPreview from '@app/assets/images/sign-in-image.png';
import ImageSignInValidatin from '@app/assets/images/sign-in-verification.png';
import ImageSignUpPreview from '@app/assets/images/sign-up-image.png';
import ImageSignUpValidation from '@app/assets/images/sign-up-verification.png';
import Logo from '@app/components/ui/logo';
import { localesCommon } from '@app/constants/locales/common';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { signUpScreen } from '@app/constants/locales/signup-screen';
import Layout from '@app/layouts/_layout';

interface ConstantType {
    signInEmailTitle: string;
    signInEmailDescription: string;
    signInCodeTitle: string;
    signInCodeDescription: string;
    signUpLogoSubTitle: string;
    signUpAgreementDescription: string;
    signUpEmailTitle: string;
    signUpEmailDescription: string;
    signUpCodeTitle: string;
    signUpCodeSubTitle: string;
    signUpCodeDescription: string;
}

interface IContentProps {
    isSignup: string | string[] | undefined;
    constants: ConstantType;
}

interface MyLoginProps {
    isCreator: boolean;
}

export default function LoginLayout(props: MyLoginProps) {
    const { t } = useTranslation();

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
        signUpCodeDescription: t(signUpScreen.features.otp_description)
    };

    const { isSignup } = useRouter().query;

    const [email, setEmail] = useState('');

    const TermsAndCondition = () => (
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

    return (
        <Layout className="min-h-screen !mt-0 !p-0">
            <div className=" h-full w-full flex flex-col lg:flex-row">
                <div className={` bg-sign-in bg-no-repeat bg-cover relative min-h-fit sm:min-h-screen order-2 lg:order-1 overflow-hidden w-full lg:w-[50%] flex flex-col justify-start`}>
                    {email ? <OtpCodeContent isSignup={isSignup} constants={constants} /> : <OtpEmailContent isSignup={isSignup} constants={constants} />}
                </div>
                <div className="relative flex flex-col order-1 lg:order-2 items-start justify-between px-8 py-7 lg:py-8 xl:pl-[90px] xl:pr-28 min-h-fit sm:min-h-screen w-full lg:max-w-[50%]">
                    <div className="mb-20 lg:mb-0">
                        <Logo isLink={false} />
                        <h1 className="body4 !text-black-800 mt-2">{constants.signUpLogoSubTitle}</h1>
                    </div>
                    {!email ? <OtpEmailInput isCreator={props.isCreator} setEmail={setEmail} isSignup={isSignup} /> : <OtpCodeComponent email={email} setEmail={setEmail} isCreator={props.isCreator} />}
                    <TermsAndCondition />
                </div>
            </div>
        </Layout>
    );
}

const OtpEmailContent = ({ isSignup, constants }: IContentProps) => {
    return (
        <>
            <div className="flex flex-col gap-4 items-center justify-center px-8 mt-28 mb-[77px] lg:max-h-[300px] text-center">
                <h1 className={cn('text-base md:text-[32px] leading-normal text-white font-semibold ', isSignup ? 'sm:w-[456px]' : 'sm:w-[431px]')}>{isSignup ? constants.signUpEmailTitle : constants.signInEmailTitle}</h1>
                <span className="font-normal text-black-200 text-xs md:text-base sm:w-[400px]">{isSignup ? constants.signUpEmailDescription : constants.signInEmailDescription}</span>
            </div>
            <div className="flex w-full justify-center lg:px-[60px] px-8 ">
                <div className="lg:h-[400px] h-[300px] w-fit">
                    <Image src={isSignup ? ImageSignUpPreview : ImageSignInPreview} alt="BetterCollected" objectFit="contain" />
                </div>
            </div>
        </>
    );
};

const OtpCodeContent = ({ isSignup, constants }: IContentProps) => {
    return (
        <>
            <div className="flex flex-col gap-4 items-center justify-center px-8 mt-28  lg:max-h-[300px] text-center">
                {isSignup && <h1 className="text-base font-semibold text-white mb-1">{constants.signUpCodeSubTitle}</h1>}
                <h1 className="text-base md:text-[32px] leading-normal text-white font-semibold sm:w-[502px]">{isSignup ? constants.signUpCodeTitle : constants.signInCodeTitle}</h1>
                <span className="font-normal text-black-200 text-xs md:text-base sm:w-[400px]">{isSignup ? constants.signUpCodeDescription : constants.signInCodeDescription}</span>
            </div>
            <div className="flex w-full justify-center lg:px-[60px] px-8 pt-8">
                <div className="lg:h-[400px] h-[300px] w-fit">
                    <Image src={isSignup ? ImageSignUpValidation : ImageSignInValidatin} alt="BetterCollected" objectFit="contain" />
                </div>
            </div>
        </>
    );
};


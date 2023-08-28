import React, { useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import OtpCodeComponent from '@Components/Login/otp-code-component';
import OtpEmailInput from '@Components/Login/otp-email-input';
import { Check } from '@mui/icons-material';

import ImageWorkspacePreview from '@app/assets/images/workspace-preview1.png';
import Logo from '@app/components/ui/logo';
import { localesCommon } from '@app/constants/locales/common';
import { signInScreen } from '@app/constants/locales/signin-screen';

interface FeatureType {
    heading: string;
    paragraphs: Array<string>;
}

interface MyLoginProps {
    features: FeatureType;
    isCreator: boolean;
}

export function SignInModal(props: MyLoginProps) {
    const features = props.features;
    const { t } = useTranslation();

    const [email, setEmail] = useState('');

    const TermsAndCondition = () => (
        <div className="body4">
            {t(signInScreen.signinAgreementDescription)}
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
        <div className="!mt-0">
            <div className="absolute top-0 left-0 w-full flex flex-col xl:flex-row ">
                <div className={`bg-brand-500 xl:rounded-l-lg relative xl:order-1 overflow-hidden w-screen xl:w-[547px] xl:h-[687px] pt-16 xl:px-[60px] xl:py-[80px] hidden xl:flex xl:flex-col xl:justify-start`}>
                    <div className="flex flex-col px-8 xl:max-h-[300px] mb-[105px]">
                        <h1 className="sh1 !text-black-100 mb-6">{features.heading}</h1>
                        {features.paragraphs.map((paragraph: string, idx: number) => (
                            <div key={idx} className="flex items-center gap-3 mb-4 last:mb-0">
                                <Check className="text-black-300" />
                                <p className="body2 !text-black-300">{paragraph}</p>
                            </div>
                        ))}
                    </div>
                    <div className="flex w-full px-8 ">
                        <div className=" h-screen xl:h-[230px] w-fit  ">
                            <Image src={ImageWorkspacePreview} alt="BetterCollected" objectFit="contain" />
                        </div>
                    </div>
                </div>
                <div className="flex flex-col order-1 !bg-brand-100 xl:order-2 items-start justify-between py-5 xl:py-0 px-8 xl:py-[28px] h-screen xl:h-[687px] w-screen xl:w-[547px]">
                    <Logo isLink={false} />
                    {!email ? <OtpEmailInput isCreator={props.isCreator} setEmail={setEmail} isModal={true} /> : <OtpCodeComponent email={email} setEmail={setEmail} isCreator={props.isCreator} isModal={true} />}
                    <TermsAndCondition />
                </div>
            </div>
        </div>
    );
}

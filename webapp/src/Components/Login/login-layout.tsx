import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import OtpCodeComponent from '@Components/Login/otp-code-component';
import OtpEmailInput from '@Components/Login/otp-email-input';
import { Check } from '@mui/icons-material';

import ImageWorkspacePreview from '@app/assets/images/workspace-preview.png';
import Logo from '@app/components/ui/logo';
import { localesCommon } from '@app/constants/locales/common';
import { signInScreen } from '@app/constants/locales/signin-screen';
import Layout from '@app/layouts/_layout';

interface FeatureType {
    heading: string;
    paragraphs: Array<string>;
}

interface MyLoginProps {
    features: FeatureType;
    isCreator: boolean;
}

export default function LoginLayout(props: MyLoginProps) {
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
        <Layout className="min-h-screen !mt-0">
            <div className="absolute h-fit top-0 left-0 w-full flex flex-col xl:flex-row">
                <div className={`bg-brand-500 relative order-2 xl:order-1 min-h-screen xl:max-h-screen overflow-hidden h-fit xl:h-full w-full xl:w-[50%] flex flex-col justify-start`}>
                    <div className="flex flex-col px-8 my-10 xl:max-h-[300px] xl:px-[94px] ">
                        <h1 className="sh1 !text-black-100 mb-6">{features.heading}</h1>
                        {features.paragraphs.map((paragraph: string, idx: number) => (
                            <div key={idx} className="flex items-center gap-3 mb-4 last:mb-0">
                                <Check className="text-black-300" />
                                <p className="body2 !text-black-300">{paragraph}</p>
                            </div>
                        ))}
                    </div>
                    <div className="flex w-full xl:px-[94px] px-8 pt-8 ">
                        <div className="xl:h-[400px] h-[300px] w-fit">
                            <Image src={ImageWorkspacePreview} alt="BetterCollected" objectFit="contain" />
                        </div>
                    </div>
                </div>
                <div className="flex flex-col order-1 xl:order-2 items-start justify-start xl:justify-center px-8 py-7 xl:py-8 xl:px-[110px] h-fit xl:h-full w-full xl:max-w-[716px]">
                    <Logo isLink={false} />
                    {!email ? <OtpEmailInput isCreator={props.isCreator} setEmail={setEmail} /> : <OtpCodeComponent email={email} setEmail={setEmail} isCreator={props.isCreator} />}
                    <TermsAndCondition />
                </div>
            </div>
        </Layout>
    );
}

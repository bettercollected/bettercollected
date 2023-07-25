import React, { useEffect, useState } from 'react';

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

    const [stepCount, setStepCount] = useState(0);

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
        <Layout className="min-h-screen  ">
            <div className="absolute h-fit top-0 left-0 w-full flex flex-col md:flex-row">
                <div className={`bg-brand-500 relative order-2 md:order-1 min-h-screen md:max-h-screen overflow-hidden h-fit md:h-full w-full md:w-[50%] flex flex-col justify-center`}>
                    <div className="flex flex-col px-8 md:max-h-[300px] my-10 md:px-[94px] ">
                        <h1 className="h4 !text-black-100 mb-6">{features.heading}</h1>
                        {features.paragraphs.map((paragraph: string, idx: number) => (
                            <div key={idx} className="flex items-center gap-3 mb-4 last:mb-0">
                                <Check className="text-black-300" />
                                <p className="text-black-300">{paragraph}</p>
                            </div>
                        ))}
                    </div>
                    <div className="flex items-center justify-center w-full">
                        <div className="relative  md:h-[400px] h-[300px] w-full  ">
                            <Image layout="fill" src={ImageWorkspacePreview} alt="BetterCollected" objectFit="contain" />
                        </div>
                    </div>
                </div>
                <div className="flex flex-col order-1 md:order-2 items-start justify-start md:justify-center px-8 py-7 md:py-8 md:px-[110px] h-fit md:h-full w-full md:max-w-[716px]">
                    <Logo isLink={false} />
                    {stepCount === 0 && <OtpEmailInput isCreator={props.isCreator} setStepCount={setStepCount} />}
                    {stepCount === 1 && <OtpCodeComponent stepCount={stepCount} setStepCount={setStepCount} />}
                    <TermsAndCondition />
                </div>
            </div>
        </Layout>
    );
}

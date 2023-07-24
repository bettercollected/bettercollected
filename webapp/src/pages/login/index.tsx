import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';
import Link from 'next/link';

import { Check } from '@mui/icons-material';
import Divider from '@mui/material/Divider';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import ImageWorkspacePreview from '@app/assets/images/workspace-preview.png';
import BetterInput from '@app/components/Common/input';
import Back from '@app/components/icons/back';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import Button from '@app/components/ui/button';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { workspaceConstant } from '@app/constants/locales/workspace';
import Layout from '@app/layouts/_layout';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { IntegrationFormProviders } from '@app/models/dtos/provider';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';
import { capitalize } from '@app/utils/stringUtils';

export async function getServerSideProps(_context: any) {
    const config = getServerSideAuthHeaderConfig(_context);
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    const locale = globalProps['_nextI18Next']['initialLocale'] === 'en' ? '' : `${globalProps['_nextI18Next']['initialLocale']}/`;
    if (checkHasCustomDomain(_context)) {
        return {
            redirect: {
                permanent: false,
                destination: `/${locale}`
            }
        };
    }

    try {
        const userStatus = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e)) ?? null;
        if (user?.roles?.includes('FORM_CREATOR')) {
            const userWorkspaceResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/mine`, config);
            const userWorkspace = (await userWorkspaceResponse?.json().catch((e: any) => e)) ?? null;
            const defaultWorkspace = userWorkspace.filter((workspace: WorkspaceDto) => workspace.ownerId === user.id && workspace?.default);
            let redirectWorkspace: WorkspaceDto | null;
            if (defaultWorkspace.length > 0) {
                redirectWorkspace = defaultWorkspace[0];
            } else {
                redirectWorkspace = userWorkspace[0];
            }
            if (!redirectWorkspace?.title || redirectWorkspace?.title === '' || redirectWorkspace?.title.toLowerCase() === 'untitled') {
                return {
                    redirect: {
                        permanent: false,
                        destination: `/${locale}${redirectWorkspace?.workspaceName}/onboarding`
                    }
                };
            }
            return {
                redirect: {
                    permanent: false,
                    destination: `/${locale}${redirectWorkspace?.workspaceName}/dashboard`
                }
            };
        }
    } catch (e) {
        console.error(e);
    }
    return {
        props: { ...globalProps }
    };
}

export const Login = () => {
    const { t } = useTranslation();

    const [email, setEmail] = useState('');
    const [otp, setOtp] = useState('');
    const [counter, setCounter] = useState(60);

    const [stepCount, setStepCount] = useState(0);

    const constants = {
        heading4: t(signInScreen.features.title),
        heading3: t(signInScreen.signIn),
        subHeading2: t(signInScreen.continueWIth),
        paragraphs: [t(signInScreen.features.feature1), t(signInScreen.features.feature2), t(signInScreen.features.feature3), t(signInScreen.features.feature4), t(signInScreen.features.feature5), t(signInScreen.features.feature6)],
        button: t(signInScreen.signUp),
        enterYourEmail: t(signInScreen.enterYourEmail),
        continue: t(signInScreen.continue),
        orSignInUsing: t(signInScreen.orSignInUsing),
        verificationTitle: t(signInScreen.verificationTitle),
        enterOtpCode: t(signInScreen.enterOtpCode),
        backButtonTitle: t(signInScreen.backButtonTitle),
        didnotReceiveCode: t(signInScreen.didNotReceiveCode)
    };

    useEffect(() => {
        if (stepCount === 0) cleanup();
    }, [stepCount]);

    const handleEmailInput = (e: any) => {
        setEmail(e.target.value);
    };

    const handleOtpChange = (e: any) => {
        setOtp(e.target.value);
    };

    const cleanup = () => {
        setOtp('');
    };

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

    const handleGoBackOnStepOne = () => {
        setStepCount(stepCount - 1);
    };

    const stepZeroContent = (
        <>
            <div className="flex flex-col order-1 md:order-2 items-start justify-start md:justify-center px-8 py-7 md:py-8 md:px-[110px] h-fit md:h-full w-full md:max-w-[716px]">
                <div className="mb-28">
                    <Logo isLink={false} />
                </div>
                <h3 className="h3 mb-[16px]">{constants.heading3}</h3>
                <div className={'flex items-center sh2 text-brand-500'}>
                    <p className="!text-black-700">{constants.subHeading2}</p>
                    <div className={'!text-brand-500'}>{constants.button}</div>
                </div>

                <p className=" mb-[8px] mt-[44px] text-black-900">{constants.enterYourEmail}</p>
                <BetterInput placeholder={constants.enterYourEmail} value={email} onChange={handleEmailInput} />
                <Button variant="solid" className={'w-full mt-[32px] mb-[40px]'} size={'large'} onClick={() => setStepCount(stepCount + 1)}>
                    {constants.continue}
                </Button>

                <Divider orientation="horizontal" flexItem className={'text-black-700 mb-[40px]'}>
                    {constants.orSignInUsing}
                </Divider>

                <div className="flex flex-col gap-[20px] mb-[60px]">
                    <FormProviderContext.Consumer>
                        {(formProviders: Array<IntegrationFormProviders>) => (
                            <div className="flex md:flex-row flex-col gap-4">
                                {formProviders.map((provider: IntegrationFormProviders) => (
                                    <ConnectWithProviderButton
                                        key={provider.providerName}
                                        type={provider.providerName === 'typeform' ? 'typeform' : 'dark'}
                                        url={`${environments.API_ENDPOINT_HOST}/auth/${provider.providerName}/basic`}
                                        text={`Sign in with ${capitalize(provider.providerName)}`}
                                        creator
                                    />
                                ))}
                            </div>
                        )}
                    </FormProviderContext.Consumer>
                </div>
                <TermsAndCondition />
            </div>
        </>
    );

    const stepOneContent = (
        <>
            <div className="flex flex-col order-1 md:order-2 items-start justify-start md:justify-center px-8 py-7 md:py-8 md:px-[110px] h-fit md:h-full w-full md:max-w-[716px]">
                <div className="mb-28">
                    <Logo isLink={false} />
                </div>
                <div className={'flex items-center cursor-pointer gap-1 hover:text-brand'} onClick={handleGoBackOnStepOne}>
                    <Back />
                    <p className={'hover:text-brand'}>{constants.backButtonTitle}</p>
                </div>
                <h3 className="h3 mt-[36px] mb-[16px]">{constants.verificationTitle}</h3>
                <div className={'flex items-center sh2 text-brand-500'}>
                    <p className="!text-black-700">{constants.subHeading2}</p>
                    <div className={'!text-brand-500'}>{constants.button}</div>
                </div>

                <p className=" mb-[8px] mt-[44px] text-black-900">{constants.enterOtpCode}</p>
                <BetterInput placeholder={constants.enterOtpCode} value={otp} onChange={handleOtpChange} />
                <Button variant="solid" className={'w-full mt-[32px] mb-[40px]'} size={'large'}>
                    {constants.continue}
                </Button>
                <div className={'flex items-center gap-2 mb-[60px] text-black-900'}>
                    <p>{constants.didnotReceiveCode}</p>
                    <>
                        {counter !== 0 && (
                            <p className="text-gray-500 cursor-not-allowed">
                                {t(buttonConstant.resendCode)} <span className={'text-brand-500'}>({counter})</span>
                            </p>
                        )}
                        {counter === 0 && (
                            <p
                                className="cursor-pointer"
                                onClick={() => {
                                    setCounter(60);
                                }}
                            >
                                {t(buttonConstant.resendCode)}
                            </p>
                        )}
                    </>
                </div>
                <TermsAndCondition />
            </div>
        </>
    );

    return (
        <Layout className="min-h-screen  ">
            <div className="absolute h-fit top-0 left-0 w-full flex flex-col md:flex-row">
                <div className={`bg-brand-500 relative order-2 md:order-1 min-h-screen md:max-h-screen overflow-hidden h-fit md:h-full w-full md:w-[50%] flex flex-col justify-center`}>
                    <div className="flex flex-col px-8 md:max-h-[300px] my-10 md:px-[94px] ">
                        <h1 className="h4 !text-black-100 mb-6">{constants.heading4}</h1>
                        {constants.paragraphs.map((paragraph, idx) => (
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
                {stepCount === 0 && stepZeroContent}
                {stepCount === 1 && stepOneContent}
            </div>
        </Layout>
    );
};

export default Login;

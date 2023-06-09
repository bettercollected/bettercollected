import React, { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import Image, { StaticImageData } from 'next/image';
import { useRouter } from 'next/router';

import GetStartedStepper from '@Components/GetStarted/Stepper';
import cn from 'classnames';

import GetStartedDataRights from '@app/assets/images/getstarted-datarights.png';
import GetStartedFormBrand from '@app/assets/images/getstarted-formbrand.png';
import GetStartedProvidersImage from '@app/assets/images/getstarted-providers.png';
import UserFitImage from '@app/assets/images/happy.png';
import UserNotFitImage from '@app/assets/images/sad.png';
import Button from '@app/components/ui/button/button';
import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { getStarted } from '@app/constants/locales/get-started';
import Layout from '@app/layouts/_layout';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export async function getServerSideProps(_context: any) {
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
    const config = getServerSideAuthHeaderConfig(_context);

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.user ?? null;
        if (user?.roles?.includes('FORM_CREATOR')) {
            const userWorkspaceResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/mine`, config);
            const userWorkspace = (await userWorkspaceResponse?.json().catch((e: any) => e)) ?? null;
            const defaultWorkspace = userWorkspace.filter((workspace: WorkspaceDto) => workspace.ownerId === user.id);
            let redirectWorkspace: WorkspaceDto | null;
            if (defaultWorkspace.length > 0) {
                redirectWorkspace = defaultWorkspace[0];
            } else {
                redirectWorkspace = userWorkspace[0];
            }
            if (!redirectWorkspace?.title || redirectWorkspace.title.toLowerCase() === 'untitled') {
                return {
                    redirect: {
                        permanent: false,
                        destination: `/${locale}/${redirectWorkspace?.workspaceName}/onboarding`
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

interface IGetStartedStep {
    id: string;
    title: string;
    description: string;
    image?: {
        url: string | StaticImageData;
        alt: string;
    } | null;
    nextButtonProps?: {
        nextBtn: {
            btnText: string;
            btnUrl?: string | null;
        };
        noBtn?: {
            btnText: string;
        };
    };
    additionalProps?: {
        text?: string | null;
        link?: string | null;
        linkText?: string | null;
    };
    additionalComponent?: React.ReactNode;
}

const GetStarted = (props: any) => {
    const router = useRouter();
    const [activeStep, setActiveStep] = React.useState(0);
    const [stepAnswers, setStepAnswers] = React.useState({});
    const [isFit, setIsFit] = React.useState(true);
    const { t } = useTranslation();
    const locale = props._nextI18Next.initialLocale === 'en' ? '' : `${props._nextI18Next.initialLocale}/`;
    useEffect(() => {
        if (activeStep >= steps.length)
            setIsFit(
                Object.values(stepAnswers)
                    .slice(1)
                    .some((answer) => answer === 'yes')
            );
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeStep]);

    const handleNext = ({ id, answer }: { id: string; answer: string }) => {
        const answerObj = { [id]: answer };
        setStepAnswers({ ...stepAnswers, ...answerObj });
        setActiveStep((prevActiveStep) => prevActiveStep + 1);
    };

    const handleBack = () => {
        if (activeStep === 0) router.push('https://bettercollected.com');
        else setActiveStep((prevActiveStep) => prevActiveStep - 1);
    };

    const signUpLink = environments.IS_IN_PRODUCTION_MODE ? `https://admin.bettercollected.com/${locale}login` : `https://bettercollected-admin.sireto.dev/${locale}login`;

    const steps: Array<IGetStartedStep> = [
        {
            id: '0-fit-step',
            title: t(getStarted.zeroFitStep.title),
            description: t(getStarted.zeroFitStep.description),
            image: null,
            nextButtonProps: {
                nextBtn: {
                    btnText: t(getStarted.zeroFitStep.buttonText),
                    btnUrl: null
                }
            },
            additionalProps: {
                text: t(getStarted.zeroFitStep.additionalProps.text),
                link: signUpLink,
                linkText: t(getStarted.zeroFitStep.additionalProps.linkedText)
            },
            additionalComponent: <Logo isCustomDomain isFooter />
        },
        {
            id: '1-form-builders',
            title: t(getStarted.formBuilder.title),
            description: t(getStarted.formBuilder.description),
            image: {
                url: GetStartedProvidersImage,
                alt: 'Providers'
            },
            nextButtonProps: {
                nextBtn: {
                    btnText: t(buttonConstant.yes),
                    btnUrl: null
                },
                noBtn: {
                    btnText: t(buttonConstant.no)
                }
            }
        },
        {
            id: '2-form-brand',
            title: t(getStarted.formBrand.title),
            description: t(getStarted.formBrand.description),
            image: {
                url: GetStartedFormBrand,
                alt: 'Form Branding'
            },
            nextButtonProps: {
                nextBtn: {
                    btnText: t(buttonConstant.yes),
                    btnUrl: null
                },
                noBtn: {
                    btnText: t(buttonConstant.no)
                }
            }
        },
        {
            id: '3-data-rights',
            title: t(getStarted.dataRights.title),
            description: t(getStarted.dataRights.description),
            image: {
                url: GetStartedDataRights,
                alt: 'Data Rights'
            },
            nextButtonProps: {
                nextBtn: {
                    btnText: t(buttonConstant.yes),
                    btnUrl: null
                },
                noBtn: {
                    btnText: t(buttonConstant.no)
                }
            }
        }
    ];

    const previewGetStartedStep = (step: IGetStartedStep) => {
        const nextButton = !!step.nextButtonProps?.nextBtn && (
            <Button size="large" onClick={() => handleNext({ id: step.id, answer: 'yes' })}>
                {step.nextButtonProps.nextBtn.btnText}
            </Button>
        );

        const noButton = !!step.nextButtonProps?.noBtn && (
            <Button size="large" onClick={() => handleNext({ id: step.id, answer: 'no' })} className="!bg-white !text-brand  border-[1px] border-brand">
                {step.nextButtonProps.noBtn.btnText}
            </Button>
        );

        const hasYesNoBoth = !!step.nextButtonProps?.nextBtn?.btnText && !!step.nextButtonProps?.noBtn?.btnText;

        return (
            <div key={step.id} className="flex  flex-col  items-center justify-center gap-12">
                {step.additionalComponent}
                <div key={step.id} className={cn('flex relative  flex-col   bg-white rounded-lg py-7 px-[19px] w-full md:w-[525px]', !step.additionalProps && 'h-[520px]')}>
                    <h1 className="text-black-900 font-semibold text-2xl mb-8">{step.title}</h1>
                    <p className={cn('body4 !text-black-700', step.id === '0-fit-step' ? 'mb-[60px]' : 'mb-10')}>{step.description}</p>
                    {!!step.image && (
                        <div className="relative h-40 mb-10 flex items-center justify-center">
                            <Image src={step.image.url} alt={step.image.alt} layout="fixed" />
                        </div>
                    )}
                    <div className={`grid grid-cols-${hasYesNoBoth ? 2 : 1} gap-6 w-full  ${!step.additionalProps && 'md:absolute bottom-6  md:w-[487px]'}`}>
                        {!!step.nextButtonProps?.noBtn && noButton}
                        {!!step.nextButtonProps?.nextBtn && (step.nextButtonProps?.nextBtn.btnUrl ? <ActiveLink href={step.nextButtonProps.nextBtn.btnUrl}>{nextButton}</ActiveLink> : nextButton)}
                    </div>
                    {!!step.additionalProps && (
                        <div className="text-center flex flex-col sm:flex-row gap-3 justify-center items-center mt-10">
                            {step.additionalProps?.text && <span>{step.additionalProps.text}</span>}
                            {step.additionalProps?.link && step.additionalProps?.linkText && (
                                <ActiveLink href={step.additionalProps.link} className="text-brand">
                                    <span>{step.additionalProps.linkText}</span>
                                </ActiveLink>
                            )}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const userIsFit = () => {
        return (
            <div className="flex flex-col items-center justify-center gap-12 mt-10">
                <div className="flex flex-col bg-white rounded-lg py-7 px-6 w-full md:w-[525px]">
                    <h1 className="text-black-900 font-semibold text-2xl mb-8">{t(getStarted.userIsFit.title)}</h1>

                    <p className="body4 !text-black-700 leading-none">{t(getStarted.userIsFit.description1)}</p>
                    <p className="body4 !text-black-700 mt-[32px] leading-none">{t(getStarted.userIsFit.description2)}</p>

                    <div className="relative h-40 my-10 flex items-center justify-center">
                        <Image src={UserFitImage} alt="User Fit" layout="fixed" />
                    </div>
                    <Button size="large" onClick={() => router.push(signUpLink)}>
                        {t(getStarted.userIsFit.buttonText)}
                    </Button>
                </div>
            </div>
        );
    };

    const userIsNotFit = () => {
        return (
            <div className="flex flex-col items-center justify-center gap-12 mt-10">
                <div className="flex flex-col bg-white rounded-lg py-7 px-6 w-full md:w-[525px]">
                    <h1 className="text-black-900 font-semibold text-2xl mb-8">{t(getStarted.userIsNotFit.title)}</h1>

                    <p className="body4 !text-black-700 leading-none">{t(getStarted.userIsNotFit.description1)}</p>
                    <p className="body4 !text-black-700 mt-[32px] leading-none">{t(getStarted.userIsNotFit.description2)}</p>

                    <div className="relative h-40 my-10 flex items-center justify-center">
                        <Image src={UserNotFitImage} alt="User not fit" layout="fixed" />
                    </div>

                    <Button size="large" onClick={() => router.push(signUpLink)}>
                        {t(getStarted.userIsNotFit.buttonText)}
                    </Button>
                </div>
            </div>
        );
    };

    return (
        <Layout showNavbar isCustomDomain isFooter className="flex justify-center" childClassName="flex flex-col justify-center items-center container my-10 gap-11">
            {activeStep < steps.length && <GetStartedStepper steps={steps.length} activeStep={activeStep} handleBack={handleBack} />}
            {steps.map((step, idx) => idx === activeStep && previewGetStartedStep(step))}
            {activeStep >= steps.length && isFit && userIsFit()}
            {activeStep >= steps.length && !isFit && userIsNotFit()}
        </Layout>
    );
};

export default GetStarted;

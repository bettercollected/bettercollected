import React, { useEffect } from 'react';

import Image, { StaticImageData } from 'next/image';
import { useRouter } from 'next/router';

import GetStartedStepper from '@Components/GetStarted/Stepper';

import GetStartedDataRights from '@app/assets/images/getstarted-datarights.png';
import GetStartedFormBrand from '@app/assets/images/getstarted-formbrand.png';
import GetStartedProvidersImage from '@app/assets/images/getstarted-providers.png';
import Button from '@app/components/ui/button/button';
import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export async function getServerSideProps(_context: any) {
    if (checkHasCustomDomain(_context)) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
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
                        destination: `/${redirectWorkspace?.workspaceName}/onboarding`
                    }
                };
            }
            return {
                redirect: {
                    permanent: false,
                    destination: `/${redirectWorkspace?.workspaceName}/dashboard`
                }
            };
        }
    } catch (e) {
        console.error(e);
    }
    return {
        props: {}
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

const GetStarted = () => {
    const router = useRouter();
    const [activeStep, setActiveStep] = React.useState(0);
    const [stepAnswers, setStepAnswers] = React.useState({});
    const [isFit, setIsFit] = React.useState(true);

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

    const signUpLink = environments.IS_IN_PRODUCTION_MODE ? 'https://admin.bettercollected.com/login' : 'https://bettercollected-admin.sireto.dev/login';

    const steps: Array<IGetStartedStep> = [
        {
            id: '0-fit-step',
            title: 'Is bettercollected right fit for you?',
            description: 'We care about your experience. Before proceeding, we assess if the app aligns with your needs. Your satisfaction is our priority.',
            image: null,
            nextButtonProps: {
                nextBtn: {
                    btnText: 'Start Exploring',
                    btnUrl: null
                }
            },
            additionalProps: {
                text: 'Already familiar with the app?',
                link: signUpLink,
                linkText: 'Sign Up Now!'
            },
            additionalComponent: <Logo isCustomDomain isFooter />
        },
        {
            id: '1-form-builders',
            title: 'Do you use online form builders?',
            description: 'Do you use online form builders like Google Form and Typeform for collecting form responses for yourself or your company?',
            image: {
                url: GetStartedProvidersImage,
                alt: 'Providers'
            },
            nextButtonProps: {
                nextBtn: {
                    btnText: 'Yes',
                    btnUrl: null
                },
                noBtn: {
                    btnText: 'No'
                }
            }
        },
        {
            id: '2-form-brand',
            title: 'Do you wish you could brand the forms better?',
            description: 'Wish you could have customer friendly form URLs and your own custom domain links that reflects your brand instead of default generated URLs.',
            image: {
                url: GetStartedFormBrand,
                alt: 'Form Branding'
            },
            nextButtonProps: {
                nextBtn: {
                    btnText: 'Yes',
                    btnUrl: null
                },
                noBtn: {
                    btnText: 'No'
                }
            }
        },
        {
            id: '3-data-rights',
            title: "Do you care about users' data rights?",
            description: "Are you a privacy respecting individual or organization which respects users' data rights provided by regulations like GDPR and CCPA?",
            image: {
                url: GetStartedDataRights,
                alt: 'Data Rights'
            },
            nextButtonProps: {
                nextBtn: {
                    btnText: 'Yes',
                    btnUrl: null
                },
                noBtn: {
                    btnText: 'No'
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
            <Button size="large" onClick={() => handleNext({ id: step.id, answer: 'no' })} className="!bg-white !text-brand hover:!text-white border-[1px] border-brand">
                {step.nextButtonProps.noBtn.btnText}
            </Button>
        );

        const hasYesNoBoth = !!step.nextButtonProps?.nextBtn?.btnText && !!step.nextButtonProps?.noBtn?.btnText;

        return (
            <div key={step.id} className="flex flex-col items-center justify-center gap-12">
                {step.additionalComponent}
                <div key={step.id} className="flex flex-col bg-white rounded-lg py-7 px-6 w-full md:w-[525px]">
                    <h1 className="text-black-900 font-semibold text-2xl mb-8">{step.title}</h1>
                    <p className="body4 !text-black-700 leading-none mb-[60px]">{step.description}</p>
                    {!!step.image && (
                        <div className="relative h-40 mb-10 flex items-center justify-center">
                            <Image src={step.image.url} alt={step.image.alt} layout="fixed" />
                        </div>
                    )}
                    <div className={`grid grid-cols-${hasYesNoBoth ? 2 : 1} gap-6 w-full`}>
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
                    <h1 className="text-black-900 font-semibold text-2xl mb-8">You are in the right place</h1>
                    <div className="min-h-[20vh]">
                        <p className="body4 !text-black-700 leading-none mb-[60px]">Sign up now and start enjoying all the amazing features and benefits that the app has to offer.</p>
                    </div>

                    <Button size="large" onClick={() => router.push(signUpLink)}>
                        Sign Up
                    </Button>
                </div>
            </div>
        );
    };

    const userIsNotFit = () => {
        return (
            <div className="flex flex-col items-center justify-center gap-12 mt-10">
                <div className="flex flex-col bg-white rounded-lg py-7 px-6 w-full md:w-[525px]">
                    <h1 className="text-black-900 font-semibold text-2xl mb-8">This app may not be perfect fit for you.</h1>
                    <div className="min-h-[20vh]">
                        <p className="body4 !text-black-700 leading-none mb-[60px]">
                            While this app may not be an exact fit, we encourage you to give it a try. It offers valuable features that could enhance your experience. Explore its potential and see if it meets your needs.
                        </p>
                    </div>

                    <Button size="large" onClick={() => router.push(signUpLink)}>
                        Give it a try
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

import React from 'react';

import Image from 'next/image';

import { Check } from '@mui/icons-material';

import ImageLoginLaptopScreen from '@app/assets/images/login-laptop-screen.png';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
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
            let redirectWorkspace;
            if (defaultWorkspace.length > 0) {
                redirectWorkspace = defaultWorkspace[0];
            } else {
                redirectWorkspace = userWorkspace[0];
            }
            return {
                redirect: {
                    permanent: false,
                    destination: `/${redirectWorkspace.workspaceName}/dashboard`
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

export const Login = () => {
    const constants = {
        heading4: 'Become a better data collector',
        heading3: 'Welcome back!',
        subHeading2: 'Continue with:',
        paragraphs: ['Review forms', 'Collect your forms', 'Easy to manage forms', 'Delete responses']
    };

    return (
        <Layout className="min-h-screen">
            <div className="absolute top-0 left-0 h-full w-full flex flex-col md:flex-row">
                <div className={`bg-brand-500 relative order-2 md:order-1 h-fit md:h-full w-full md:w-[50%] flex flex-col justify-center`}>
                    <div className="flex flex-col px-8 py-7 md:px-[94px] md:py-[92px]">
                        <h1 className="h4 !text-black-100 mb-6">{constants.heading4}</h1>
                        {constants.paragraphs.map((paragraph, idx) => (
                            <div key={idx} className="flex items-center gap-3 mb-4 last:mb-0">
                                <Check className="text-black-300" />
                                <p className="text-black-300">{paragraph}</p>
                            </div>
                        ))}
                    </div>
                    <div className="flex items-center justify-center w-full">
                        <div className="relative h-[244px] w-[320px] md:h-[340px] md:w-[446px]">
                            <Image layout="fill" src={ImageLoginLaptopScreen} alt="BetterCollected" />
                        </div>
                    </div>
                </div>
                <div className="flex flex-col order-1 md:order-2 items-start justify-start px-8 py-7 md:py-8 md:px-[110px] h-fit md:h-full w-full md:w-[50%]">
                    <div className="mb-28">
                        <Logo />
                    </div>
                    <h3 className="h3 mb-4">{constants.heading3}</h3>
                    <p className="sh2 mb-12 !text-black-700">{constants.subHeading2}</p>

                    <div className="flex flex-col gap-[20px] mb-[60px]">
                        {environments.ENABLE_GOOGLE && <ConnectWithProviderButton type="dark" url={`${environments.API_ENDPOINT_HOST}/auth/google/basic`} text="Sign in with Google" creator />}
                        {environments.ENABLE_TYPEFORM && <ConnectWithProviderButton type="typeform" url={`${environments.API_ENDPOINT_HOST}/auth/typeform/basic`} text="Sign in with Typeform" creator />}
                    </div>

                    <div className="body4">
                        By signing in, you agree to our
                        <a href="https://bettercollected.com/terms-of-service" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline text-brand-500 hover:text-brand-600">
                            Terms of Service
                        </a>
                        and
                        <a href="https://bettercollected.com/privacy-policy" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline text-brand-500 hover:text-brand-600">
                            Privacy Policy
                        </a>
                        .
                    </div>
                </div>
            </div>
        </Layout>
    );
};

export default Login;

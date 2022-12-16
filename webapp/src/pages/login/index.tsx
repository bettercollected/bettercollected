import React from 'react';

import Image from 'next/image';

import ConnectWithGoogleButton from '@app/components/login/login-with-google-button';
import environments from '@app/configs/environments';
import ContentLayout from '@app/layouts/_content-layout';
import globalServerProps from '@app/lib/serverSideProps';

export async function getServerSideProps(_context: any) {
    const globalProps = (await globalServerProps(_context)).props;
    return {
        props: {
            ...globalProps
        }
    };
}

export const Login = () => {
    return (
        <div className="relative">
            <ContentLayout className="!pt-0 relative bg-[#FBFBFB]">
                <div className="absolute overflow-hidden inset-0">
                    <div className="absolute top-[60%] left-[-100px] w-[359px] h-[153px] bg-gradient-to-r from-orange-200 via-orange-300 to-orange-400 rotate-90 blur-dashboardBackground opacity-[20%]" />
                    <div className="absolute top-[35%] left-[65%] w-[765px] h-[765px] bg-gradient-to-r from-cyan-300 via-sky-300 to-cyan-400 blur-dashboardBackground opacity-[15%]" />
                    <div className="absolute bottom-0 left-[50%] w-[599px] h-[388px] bg-gradient-to-r from-rose-200 via-rose-300 to-rose-400 rotate-180 blur-dashboardBackground opacity-[20%]" />
                </div>
            </ContentLayout>
            <div className="absolute top-0 left-0 h-full w-full flex flex-start">
                <div className=" w-full lg:min-w-[1024px]  flex items-center justify-center flex-col space-y-8">
                    <div className="flex-col flex items-center">
                        <div className="flex items-start space-x-2">
                            <Image src="/bettercollected-logo.png" alt="Logo" height="30px" width="30px" />
                            <div className="flex text-3xl font-bold">
                                Better<p className="text-blue-500">Collected.</p>
                            </div>
                        </div>
                        <div className="text-base text-[#555555]">Collect forms responsibly !!</div>
                    </div>
                    <div className="flex flex-col justify-center items-center text-[#555555] space-y-2">
                        <div className="text-3xl font-bold">Welcome back, Collector</div>
                    </div>
                    <ConnectWithGoogleButton text="Sign In with google" />
                    <div className="text-lg text-[#555555]">
                        Don&apos;t have an account?{' '}
                        <a href={`${environments.API_ENDPOINT_HOST}/auth/google/basicAuth`} className="ml-2 text-blue-500 cursor-pointer">
                            {' '}
                            Sign Up
                        </a>
                    </div>

                    <div className="text-[11px] text-[#808080]">
                        By signing in, you agree to our
                        <a href={environments.TERMS_AND_CONDITIONS} target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline">
                            Terms of Service
                        </a>
                        and
                        <a href={environments.PRIVACY_POLICY} target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline">
                            Privacy Policy
                        </a>
                        .
                    </div>
                </div>

                <div className={`h-full side w-full hidden lg:flex`}></div>
            </div>
        </div>
    );
};

export default Login;

import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import OtpCodeComponent from '@Components/Login/otp-code-component';
import OtpEmailInput from '@Components/Login/otp-email-input';

import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Logo from '@app/components/ui/logo';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface ResponderLoginProps {
    workspaceId: string;
    redirectTo: string;
}

export default function ResponderLoginPage(props: ResponderLoginProps) {
    const [email, setEmail] = useState('');

    const router = useRouter();
    const auth = useAppSelector(selectAuth);

    useEffect(() => {
        if (auth.id && props.redirectTo) {
            router.push(props.redirectTo);
        }
    }, [auth.id]);

    if (auth.isLoading || (auth.id && props.redirectTo)) return <FullScreenLoader />;
    return (
        <div className="min-h-screen flex flex-col justify-center md:justify-start items-center min-w-screen bg-gradient-to-b from-[#B3D2FF] to-[#66A2FB] ">
            <div className="md:my-24  max-w-screen md:max-w-[496px] w-full justify-center h-screen md:h-auto px-12 py-8 flex flex-col items-center bg-white md:rounded-xl">
                <Logo isLink={false} />
                <h1 className="body4 !text-black-800 mt-2 mb-8">Privacy-friendly form builder</h1>
                {!email ? <OtpEmailInput isCreator={false} workspaceId={props.workspaceId} setEmail={setEmail} isSignup={'false'} /> : <OtpCodeComponent workspaceId={props.workspaceId} email={email} setEmail={setEmail} isCreator={false} />}
                <TermsAndCondition />
            </div>
        </div>
    );
}

const TermsAndCondition = () => {
    return (
        <div className="body4 mt-6 text-center">
            By continuing you agree to our <br />
            <a href="https://bettercollected.com/terms-of-service" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline text-brand-500 hover:text-brand-600">
                Terms of service
            </a>
            and
            <a href="https://bettercollected.com/privacy-policy" target="_blank" rel="noreferrer" className="mx-1 cursor-pointer underline text-brand-500 hover:text-brand-600">
                Privacy Policy
            </a>
            .
        </div>
    );
};

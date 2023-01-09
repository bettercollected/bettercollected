import React from 'react';

import { useTranslation } from 'next-i18next';

import LandingPageSectionContainer from '@app/components/landingpage/LandingPageSectionContainer';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';

export default function Waitlist() {
    const { t } = useTranslation();

    return (
        <LandingPageSectionContainer sectionId="sign-up">
            <div className="min-h-screen w-full h-full flex flex-col justify-center items-center">
                <h1 className="text-4xl tracking-tight leading-10 font-extrabold sm:text-5xl sm:leading-none md:text-6xl">
                    Become a <span className="text-blue-500">Better Collector</span>
                </h1>
                <p className="text-lg text-grey mt-6 p-0">Request a demo and we&apos;ll keep you updated with our progress</p>
                <div className="mt-5 sm:mt-8 sm:flex justify-start w-full md:w-fit">
                    <div className="rounded-md shadow w-full">
                        <ActiveLink
                            href={environments.WAITLIST_FORM_NAVIGATION_URL}
                            className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base leading-6 font-medium rounded-md text-white bg-blue-500 hover:bg-blue-600 focus:outline-none focus:border-indigo-700 focus:shadow-outline-indigo transition duration-150 ease-in-out md:py-4 md:text-lg md:px-20"
                        >
                            Request a demo
                        </ActiveLink>
                    </div>
                </div>
                {/* <p className="text-lg text-dark mt-6 p-0">
                    First <span className="text-blue-500">100 people</span> on the waitlist will receive <span className="font-bold">FREE Lifetime</span> subscription.
                </p> */}
            </div>
        </LandingPageSectionContainer>
    );
}

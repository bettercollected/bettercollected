import React, { useEffect } from 'react';

import { useTranslation } from 'next-i18next';

import Cal, { getCalApi } from '@calcom/embed-react';

import bettercollected from '@app/assets/svgs/bettercollected.svg';
import LandingPageSectionContainer from '@app/components/landingpage/LandingPageSectionContainer';
import Image from '@app/components/ui/image';

export default function Banner() {
    const { t } = useTranslation();

    useEffect(() => {
        (async function () {
            const cal = await getCalApi();
            cal('ui', {
                theme: 'dark',
                styles: {
                    branding: { brandColor: '#000000' }
                }
            });
        })();
    }, []);

    return (
        <LandingPageSectionContainer sectionId="banner">
            <div className="grid grid-flow-col grid-rows-2 sm:grid-rows-1 sm:grid-cols-2 gap-6 py-3 md:py-0">
                <div className="flex items-center justify-start">
                    <div className="text-left">
                        <h2 className="text-4xl tracking-tight leading-10 font-extrabold text-gray-900 sm:text-5xl sm:leading-none md:text-6xl">
                            Collect form responses
                            <br />
                            <span className="text-blue-500">responsibly.</span>
                        </h2>
                        <p className="mt-3 text-base text-gray-500 sm:mt-5 sm:text-lg sm:max-w-xl sm:mx-auto md:mt-5 md:text-xl lg:mx-0">Empower your form responders to view their collected data and exercise their data rights.</p>
                        <div data-cal-link="betterCollected" className="mt-5 cursor-pointer sm:mt-8 sm:inline-flex justify-start">
                            <div data-cal-link="betterCollected" className="rounded-md shadow">
                                <div
                                    data-cal-link="betterCollected"
                                    className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base leading-6 font-medium rounded-md text-white bg-blue-500 hover:bg-blue-600 focus:outline-none focus:border-indigo-700 focus:shadow-outline-indigo transition duration-150 ease-in-out md:py-4 md:text-lg md:px-10"
                                >
                                    Request a demo
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="flex items-center justify-center md:justify-end w-full object-cover h-fit lg:w-full md:h-max bg-cover bg-center">
                    <Image src={bettercollected} alt="BetterCollected." />
                </div>
            </div>
        </LandingPageSectionContainer>
    );
}

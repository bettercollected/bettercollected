import React from 'react';

import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';

import { ShareIcon } from '@app/components/icons/share-icon';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Image from '@app/components/ui/image';
import MarkdownText from '@app/components/ui/markdown-text';
import ContentLayout from '@app/layouts/_content-layout';
import { CompanyJsonDto } from '@app/models/dtos/customDomain';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IDashboardContainer {
    companyJson: CompanyJsonDto | null;
}

export default function DashboardContainer({ companyJson }: IDashboardContainer) {
    if (!companyJson) return <FullScreenLoader />;

    return (
        <div className="relative">
            <div className="product-box">
                <div data-aos="fade-up" className="product-image relative h-44 w-full overflow-hidden md:h-80 xl:h-[350px]">
                    <Image src={companyJson.companyBanner} layout="fill" objectFit="cover" objectPosition="center" alt={companyJson.companyTitle} />
                </div>
            </div>
            <ContentLayout className="!pt-0 relative bg-[#FBFBFB]">
                <div className="absolute overflow-hidden inset-0">
                    <div className="absolute top-[60%] left-[-100px] w-[359px] h-[153px] bg-gradient-to-r from-orange-200 via-orange-300 to-orange-400 rotate-90 blur-dashboardBackground opacity-[20%]" />
                    <div className="absolute top-[35%] left-[65%] w-[765px] h-[765px] bg-gradient-to-r from-cyan-300 via-sky-300 to-cyan-400 blur-dashboardBackground opacity-[15%]" />
                    <div className="absolute bottom-0 left-[50%] w-[599px] h-[388px] bg-gradient-to-r from-rose-200 via-rose-300 to-rose-400 rotate-180 blur-dashboardBackground opacity-[20%]" />
                </div>
                <div className="product-box">
                    <div className="product-image absolute border-[1px] border-neutral-300 hover:border-neutral-400 rounded-full z-10 h-24 w-24 sm:h-32 sm:w-32 md:h-40 md:w-40 xl:h-40 xl:w-40 2xl:h-[180px] 2xl:w-[180px] overflow-hidden -top-12 sm:-top-16 md:-top-20 xl:-top-[88px] 2xl:-top-24">
                        <Image src={companyJson.companyProfile} layout="fill" objectFit="contain" alt={companyJson.companyTitle} />
                    </div>
                </div>
                <div className="relative h-full w-full mt-12 sm:mt-16 md:mt-20 xl:mt-[88px] 2xl:mt-24">
                    <div className="py-4 md:py-6 xl:py-8 2xl:py-12 w-full md:w-9/12 xl:w-4/6 2xl:w-3/6">
                        <h1 className="font-semibold text-darkGrey text-xl sm:text-2xl md:text-3xl xl:text-4xl 2xl:text-[40px]">{companyJson.companyTitle}</h1>
                        <MarkdownText description={companyJson.companyDescription} contentStripLength={250} markdownClassName="pt-3 md:pt-7 text-base text-grey" textClassName="text-base" />
                    </div>
                </div>
                <div className="relative flex flex-col w-full">
                    <div className="flex flex-row items-center justify-between">
                        <h2 className="font-semibold text-darkGrey text-lg sm:text-xl md:text-2xl xl:text-3xl">Forms</h2>
                        <Autocomplete size="small" disablePortal id="combo-box-demo" options={[]} sx={{ width: 250 }} renderInput={(params) => <TextField {...params} label="Search forms..." />} />
                    </div>
                    <div className="pt-3 md:pt-7">
                        <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                            {[1, 2, 3, 4, 5, 6].map((form) => (
                                <div key={form} className="flex flex-row items-center gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-md transition cursor-pointer bg-white rounded-[20px]">
                                    <div className="flex flex-col">
                                        <p className="text-xl text-grey mb-4 p-0">Community Manager Summer 2022</p>
                                        <p className="text-base text-softBlue m-0 p-0">
                                            {toEndDottedStr(
                                                'This is a description or info necessary for the profile this is a description or info necessary for the profile this is a description or info necessary for the profile limited to X characters.',
                                                200
                                            )}
                                        </p>
                                    </div>
                                    <div className="p-2 border-[1px] border-white hover:border-neutral-100 hover:shadow rounded-md">
                                        <ShareIcon width={19} height={19} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </ContentLayout>
        </div>
    );
}

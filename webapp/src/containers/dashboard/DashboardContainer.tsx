import React, { useMemo } from 'react';

import { Logout } from '@app/components/icons/logout-icon';
import { useModal } from '@app/components/modal-views/context';
import SubmissionTabContainer from '@app/components/submissions-tab/submissions-tab-container';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Image from '@app/components/ui/image';
import MarkdownText from '@app/components/ui/markdown-text';
import ContentLayout from '@app/layouts/_content-layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { authApi, useGetStatusQuery, useLazyGetLogoutQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

interface IDashboardContainer {
    workspace: WorkspaceDto;
}

export default function DashboardContainer({ workspace }: IDashboardContainer) {
    const [trigger] = useLazyGetLogoutQuery();

    const authStatus = useGetStatusQuery('status');

    const { openModal } = useModal();

    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select('status'), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);

    if (!workspace || authStatus.isLoading) return <FullScreenLoader />;

    const handleLogout = async () => {
        trigger().finally(() => {
            authStatus.refetch();
        });
    };

    const handleCheckMyData = () => {
        openModal('LOGIN_VIEW');
    };

    return (
        <div className="relative">
            <div className="product-box">
                <div data-aos="fade-up" className="product-image relative h-44 w-full overflow-hidden md:h-80 xl:h-[380px]">
                    <Image src={workspace.bannerImage} priority layout="fill" objectFit="contain" objectPosition="center" alt={workspace?.title} />
                </div>
            </div>
            <ContentLayout className="!pt-0 relative bg-[#FBFBFB]">
                <div className="absolute overflow-hidden inset-0">
                    <div className="absolute top-[60%] left-[-100px] w-[359px] h-[153px] bg-gradient-to-r from-orange-200 via-orange-300 to-orange-400 rotate-90 blur-dashboardBackground opacity-[20%]" />
                    <div className="absolute top-[35%] left-[65%] w-[765px] h-[765px] bg-gradient-to-r from-cyan-300 via-sky-300 to-cyan-400 blur-dashboardBackground opacity-[15%]" />
                    <div className="absolute bottom-0 left-[50%] w-[599px] h-[388px] bg-gradient-to-r from-rose-200 via-rose-300 to-rose-400 rotate-180 blur-dashboardBackground opacity-[20%]" />
                </div>
                <div className="flex justify-between items-center">
                    <div className="product-box">
                        <div className="product-image bg-white absolute border-[1px] border-neutral-300 hover:border-neutral-400 rounded-full z-10 h-24 w-24 sm:h-32 sm:w-32 md:h-40 md:w-40 xl:h-40 xl:w-40 2xl:h-[180px] 2xl:w-[180px] overflow-hidden -top-12 sm:-top-16 md:-top-20 xl:-top-[88px] 2xl:-top-24">
                            <Image src={workspace.profileImage} layout="fill" objectFit="contain" alt={workspace.title} />
                        </div>
                    </div>
                    <div className="mt-2 mb-0 flex items-center">
                        {!!selectGetStatus.error ? (
                            <Button variant="solid" className="ml-3 !px-3 !rounded-xl !bg-blue-500" onClick={handleCheckMyData}>
                                Check My data
                            </Button>
                        ) : (
                            <>
                                {!!selectGetStatus.data.payload.content.user.sub && (
                                    <div className="py-3 px-5 hidden sm:flex rounded-full text-gray-700 border-solid italic border-[1px] border-[#eaeaea]">{selectGetStatus.data.payload.content.user.sub}</div>
                                )}
                                <Button variant="solid" className="ml-3 !px-3 !rounded-xl !bg-[#ffe0e0]" onClick={handleLogout}>
                                    <span className="w-full flex gap-2 items-center justify-center">
                                        <Logout height={20} width={20} className="!rounded-xl !text-[#e60000]" />
                                        <span className="!text-[#e60000]">Sign off</span>
                                    </span>
                                </Button>
                            </>
                        )}
                    </div>
                </div>

                <div className="relative h-full w-full mt-10 sm:mt-16 md:mt-20 xl:mt-[88px] 2xl:mt-24">
                    <div className="py-4 md:py-6 xl:py-8 2xl:py-12 w-full md:w-9/12 xl:w-4/6 2xl:w-3/6">
                        <h1 className="font-semibold text-darkGrey text-xl sm:text-2xl md:text-3xl xl:text-4xl 2xl:text-[40px]">{workspace.title}</h1>
                        <MarkdownText description={workspace.description} contentStripLength={1000} markdownClassName="pt-3 md:pt-7 text-base text-grey" textClassName="text-base" />
                    </div>
                </div>
                <SubmissionTabContainer workspaceId={workspace.id} showResponseBar={!!selectGetStatus.error} />
            </ContentLayout>
        </div>
    );
}

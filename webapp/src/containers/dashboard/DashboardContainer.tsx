import React, { useMemo } from 'react';

import { HomeIcon } from '@app/components/icons/home';
import { Logout } from '@app/components/icons/logout-icon';
import { useModal } from '@app/components/modal-views/context';
import SubmissionTabContainer from '@app/components/submissions-tab/submissions-tab-container';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Image from '@app/components/ui/image';
import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import MarkdownText from '@app/components/ui/markdown-text';
import environments from '@app/configs/environments';
import ContentLayout from '@app/layouts/_content-layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { authApi, useGetStatusQuery, useLazyGetLogoutQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

interface IDashboardContainer {
    workspace: WorkspaceDto;
    isCustomDomain: Boolean;
}

export default function DashboardContainer({ workspace, isCustomDomain }: IDashboardContainer) {
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
        openModal('LOGIN_VIEW', { isCustomDomain: true });
    };

    const Footer = () => {
        return (
            <div className="absolute left-0 bottom-0 w-full flex flex-col justify-start md:flex-row md:justify-between md:items-center px-6 sm:px-8 lg:px-12 py-2 border-t-[1.5px] border-[#eaeaea] bg-transparent drop-shadow-main mb-0">
                <div className="flex justify-between mb-4">
                    <ActiveLink target={'_blank'} className="mt-6 md:mt-0 text-sm md:text-lg mr-6 hover:text-gray-600" href={workspace.terms_of_service_url ?? ''}>
                        Terms of service
                    </ActiveLink>
                    <ActiveLink target={'_blank'} className="mt-6 md:mt-0 text-sm md:text-lg hover:text-gray-600" href={workspace.privacy_policy_url ?? ''}>
                        Privacy Policy
                    </ActiveLink>
                </div>
                {isCustomDomain && (
                    <div className="mb-2">
                        <p>Powered by</p>
                        <Logo className="!text-lg" />
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="relative min-h-screen">
            <div>
                <div className="product-image relative h-44 w-full overflow-hidden md:h-80 xl:h-[380px]">
                    {workspace.bannerImage && <Image src={workspace.bannerImage} priority layout="fill" objectFit="contain" objectPosition="center" alt={workspace?.title} />}
                </div>
            </div>
            <ContentLayout className="!pt-0 relative min-h-screen bg-[#FBFBFB] pb-40">
                <div className="absolute overflow-hidden inset-0">
                    <div className="absolute top-[60%] left-[-100px] w-[359px] h-[153px] bg-gradient-to-r from-orange-200 via-orange-300 to-orange-400 rotate-90 blur-dashboardBackground opacity-[20%]" />
                    <div className="absolute top-[35%] left-[65%] w-[765px] h-[765px] bg-gradient-to-r from-cyan-300 via-sky-300 to-cyan-400 blur-dashboardBackground opacity-[15%]" />
                    <div className="absolute bottom-0 left-[50%] w-[599px] h-[388px] bg-gradient-to-r from-rose-200 via-rose-300 to-rose-400 rotate-180 blur-dashboardBackground opacity-[20%]" />
                </div>
                <div className="flex justify-between items-center">
                    <div className="product-box">
                        <div className="product-image bg-white absolute border-[1px] border-neutral-300 hover:border-neutral-400 rounded-full z-10 h-24 w-24 sm:h-32 sm:w-32 md:h-40 md:w-40 xl:h-40 xl:w-40 2xl:h-[180px] 2xl:w-[180px] overflow-hidden -top-12 sm:-top-16 md:-top-20 xl:-top-[88px] 2xl:-top-24">
                            {workspace.profileImage && <Image src={workspace.profileImage} layout="fill" objectFit="contain" alt={workspace.title} />}
                        </div>
                    </div>
                    <div className="mt-2 mb-0 flex items-center">
                        {!!selectGetStatus.error ? (
                            <Button variant="solid" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleCheckMyData}>
                                Check My data
                            </Button>
                        ) : (
                            <>
                                {selectGetStatus.data.payload.content.user.id === workspace.ownerId && (
                                    <a href={`${environments.CLIENT_HOST.includes('localhost') ? 'http://' : 'https://'}${environments.CLIENT_HOST}/${workspace.workspaceName}/dashboard`} className="rounded-xl mr-5 !bg-blue-600 z-10 !text-white px-5 py-3">
                                        <div className=" flex space-x-4">
                                            <HomeIcon className="w-[20px] h-[20px]" />
                                            <div className="hidden md:flex">Go To Dashboard</div>
                                        </div>
                                    </a>
                                )}
                                {!!selectGetStatus.data.payload.content.user.sub && (
                                    <>
                                        <div className="px-5 py-3 bg-gray-100 md:hidden mr-2 md:mr-5 text-gray-800 rounded-xl capitalize">{selectGetStatus.data.payload.content.user.sub[0]}</div>
                                        <div className="py-3 px-5 hidden sm:flex rounded-full text-gray-700 border-solid italic border-[1px] border-[#eaeaea]">{selectGetStatus.data.payload.content.user.sub}</div>
                                    </>
                                )}
                                <Button variant="solid" className="ml-3 !px-3 !py-6 !rounded-xl !bg-[#ffe0e0]" onClick={handleLogout}>
                                    <span className="w-full flex gap-2 items-center justify-center">
                                        <Logout height={20} width={20} className="!rounded-xl !text-[#e60000]" />
                                        <span className="!text-[#e60000] hidden md:flex">Sign off</span>
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
                <SubmissionTabContainer workspace={workspace} workspaceId={workspace.id} showResponseBar={!!selectGetStatus.error} />
                <Footer />
            </ContentLayout>
        </div>
    );
}

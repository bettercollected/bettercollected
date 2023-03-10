import React, { useMemo } from 'react';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import ProfileImageComponent from '@app/components/dashboard/profile-image';
import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import { HomeIcon } from '@app/components/icons/home';
import { Logout } from '@app/components/icons/logout-icon';
import WorkspaceFooter from '@app/components/layout/workspace-footer';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import WorkspaceHeader from '@app/components/workspace/workspace-header';
import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { authApi, useGetStatusQuery, useLazyGetLogoutQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

interface IDashboardContainer {
    workspace: WorkspaceDto;
    isCustomDomain: boolean;
}

export interface BannerImageComponentPropType {
    workspace: WorkspaceDto;
    isFormCreator: boolean;
}

export default function DashboardContainer({ workspace, isCustomDomain }: IDashboardContainer) {
    const [trigger] = useLazyGetLogoutQuery();

    const authStatus = useGetStatusQuery('status');
    const { openModal } = useModal();

    if (!workspace || authStatus.isLoading) return <FullScreenLoader />;

    const isFormCreator = authStatus.isSuccess && authStatus?.data?.user?.id === workspace?.ownerId;

    const handleLogout = async () => {
        trigger().finally(() => {
            authStatus.refetch();
        });
    };

    const handleCheckMyData = () => {
        openModal('LOGIN_VIEW', { isCustomDomain: true });
    };

    return (
        <div className="relative min-h-screen">
            <div className="relative overflow-hidden h-44 w-full md:h-80 xl:h-[380px] bannerdiv">
                <BannerImageComponent workspace={workspace} isFormCreator={isFormCreator} />
            </div>
            <Layout className="!pt-0 relative min-h-screen bg-[#FBFBFB] pb-40">
                <div className="flex justify-between items-center">
                    <ProfileImageComponent workspace={workspace} isFormCreator={isFormCreator} />
                    <div className="mt-2 mb-0 flex items-center">
                        {!!authStatus.error ? (
                            <Button variant="solid" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleCheckMyData}>
                                Check My Data
                            </Button>
                        ) : (
                            <>
                                {isFormCreator && (
                                    <a
                                        target="_blank"
                                        referrerPolicy="no-referrer"
                                        href={`${environments.CLIENT_HOST.includes('localhost') ? 'http://' : 'https://'}${environments.CLIENT_HOST}/${workspace.workspaceName}/dashboard`}
                                        className="rounded-xl mr-5 !bg-blue-600 z-10 !text-white px-5 py-3"
                                        rel="noreferrer"
                                    >
                                        <div className=" flex space-x-4">
                                            <HomeIcon className="w-[20px] h-[20px]" />
                                            <div className="hidden md:flex">Go To Dashboard</div>
                                        </div>
                                    </a>
                                )}
                                {!!authStatus.data?.user.sub && (
                                    <>
                                        <div className="px-5 py-3 bg-gray-100 md:hidden mr-2 md:mr-5 text-gray-800 rounded-xl capitalize">{authStatus.data.user.sub[0]}</div>
                                        <div className="py-3 px-5 hidden sm:flex rounded-full text-gray-700 border-solid italic border-[1px] border-[#eaeaea]">{authStatus.data.user.sub}</div>
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
                <WorkspaceHeader workspace={workspace} />
                <FormsAndSubmissionsTabContainer workspace={workspace} workspaceId={workspace.id} showResponseBar={!!authStatus.error} />
                <WorkspaceFooter workspace={workspace} isCustomDomain={isCustomDomain} />
            </Layout>
        </div>
    );
}

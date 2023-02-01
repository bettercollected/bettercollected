import React, { useMemo } from 'react';

import ModeEditIcon from '@mui/icons-material/ModeEdit';

import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import { HomeIcon } from '@app/components/icons/home';
import { Logout } from '@app/components/icons/logout-icon';
import WorkspaceFooter from '@app/components/layout/workspace-footer';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Image from '@app/components/ui/image';
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

    return (
        <div className="relative min-h-screen">
            <div>
                <div className="product-image relative h-44 w-full overflow-hidden md:h-80 xl:h-[380px]">
                    {workspace.bannerImage && <Image src={workspace.bannerImage} priority layout="fill" objectFit="contain" objectPosition="center" alt={workspace?.title} />}
                    {selectGetStatus.data?.payload.content.user.id === workspace.ownerId && (
                        <div className="absolute bottom-4 right-4">
                            <div className="p-1 ml-2 my-19 bg-blue-600 hover:bg-blue-700 cursor-pointer rounded-md">
                                <ModeEditIcon className="!w-5 !h-5 text-white" />
                            </div>
                        </div>
                    )}
                </div>
            </div>
            <Layout className="!pt-0 relative min-h-screen bg-[#FBFBFB] pb-40">
                <div className="flex justify-between items-center">
                    <div className="product-box">
                        <div className="product-image bg-white absolute border-[1px] border-neutral-300 hover:border-neutral-400 rounded-full z-10 h-24 w-24 sm:h-32 sm:w-32 md:h-40 md:w-40 xl:h-40 xl:w-40 2xl:h-[180px] 2xl:w-[180px] overflow-hidden -top-12 sm:-top-16 md:-top-20 xl:-top-[88px] 2xl:-top-24">
                            {workspace.profileImage && <Image src={workspace.profileImage} layout="fill" objectFit="contain" alt={workspace.title} />}
                        </div>
                    </div>
                    <div className="mt-2 mb-0 flex items-center">
                        {!!selectGetStatus.error ? (
                            <Button variant="solid" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleCheckMyData}>
                                Check My Data
                            </Button>
                        ) : (
                            <>
                                {selectGetStatus.data?.payload?.content.user.id === workspace.ownerId && (
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
                <WorkspaceHeader workspace={workspace} />
                <FormsAndSubmissionsTabContainer workspace={workspace} workspaceId={workspace.id} showResponseBar={!!selectGetStatus.error} />
                <WorkspaceFooter workspace={workspace} isCustomDomain={isCustomDomain} />
            </Layout>
        </div>
    );
}

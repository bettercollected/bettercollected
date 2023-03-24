import React from 'react';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import ProfileImageComponent from '@app/components/dashboard/profile-image';
import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import WorkspaceFooter from '@app/components/layout/workspace-footer';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import WorkspaceLoginMenuItems from '@app/components/workspace-login-menu';
import WorkspaceHeader from '@app/components/workspace/workspace-header';
import DynamicContainer from '@app/containers/DynamicContainer';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery, useLazyGetLogoutQuery } from '@app/store/auth/api';

interface IDashboardContainer {
    workspace: WorkspaceDto;
    isCustomDomain: boolean;
}

export interface BannerImageComponentPropType {
    workspace: WorkspaceDto;
    isFormCreator: boolean;
}

export default function WorkspaceHomeContainer({ workspace, isCustomDomain }: IDashboardContainer) {
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
        <>
            <Layout className="!pt-0 relative min-h-screen bg-[#FBFBFB] pb-10 flex justify-center">
                <DynamicContainer>
                    <div className="min-h-screen">
                        <div className="relative overflow-hidden rounded-b-3xl h-44 w-full md:h-80 xl:h-[380px] bannerdiv">
                            <BannerImageComponent workspace={workspace} isFormCreator={isFormCreator} />
                        </div>
                        <div className="hidden justify-between items-start py-10 gap-6 md:flex">
                            <ProfileImageComponent workspace={workspace} isFormCreator={isFormCreator} />
                            <WorkspaceHeader workspace={workspace} />

                            {!!authStatus.error ? (
                                <Button variant="solid" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleCheckMyData}>
                                    Check My Data
                                </Button>
                            ) : (
                                <WorkspaceLoginMenuItems workspace={workspace} authStatus={authStatus} isFormCreator={isFormCreator} handleLogout={handleLogout} />
                            )}
                        </div>
                        <div className="block md:hidden">
                            <div className="flex justify-between items-start py-10 gap-6">
                                <ProfileImageComponent workspace={workspace} isFormCreator={isFormCreator} />

                                {!!authStatus.error ? (
                                    <Button variant="solid" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleCheckMyData}>
                                        Check My Data
                                    </Button>
                                ) : (
                                    <WorkspaceLoginMenuItems workspace={workspace} authStatus={authStatus} isFormCreator={isFormCreator} handleLogout={handleLogout} />
                                )}
                            </div>
                            <WorkspaceHeader workspace={workspace} />
                        </div>
                        <FormsAndSubmissionsTabContainer workspace={workspace} workspaceId={workspace.id} showResponseBar={!!authStatus.error} />
                    </div>
                    <WorkspaceFooter workspace={workspace} isCustomDomain={isCustomDomain} />
                </DynamicContainer>
            </Layout>
        </>
    );
}

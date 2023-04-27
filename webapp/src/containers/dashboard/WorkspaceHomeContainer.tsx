import React, { useEffect } from 'react';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import ProfileImageComponent from '@app/components/dashboard/profile-image';
import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import WorkspaceFooter from '@app/components/layout/workspace-footer';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import WorkspaceHeader from '@app/components/workspace/workspace-header';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { useAppDispatch } from '@app/store/hooks';
import { setWorkspace } from '@app/store/workspaces/slice';

interface IDashboardContainer {
    workspace: WorkspaceDto;
    isCustomDomain: boolean;
}

export interface BannerImageComponentPropType {
    workspace: WorkspaceDto;
    isFormCreator: boolean;
}

export default function WorkspaceHomeContainer({ workspace, isCustomDomain }: IDashboardContainer) {
    const authStatus = useGetStatusQuery('status');

    const dispatch = useAppDispatch();

    useEffect(() => {
        if (workspace.id) {
            dispatch(setWorkspace(workspace));
        }
    }, [workspace]);

    if (!workspace) return <FullScreenLoader />;

    const isFormCreator = authStatus.isSuccess && authStatus?.data?.user?.id === workspace?.ownerId;

    return (
        <Layout showNavbar checkMyDataEnabled className="!p-0 min-h-screen bg-[#FBFBFB] pb-10 flex flex-col justify-center">
            <div className="min-h-screen">
                <div className="relative overflow-hidden w-full">
                    <BannerImageComponent workspace={workspace} isFormCreator={isFormCreator} />
                </div>
                <div className="hidden justify-between items-start py-10 gap-6 md:flex px-5 lg:px-10 xl:px-20">
                    <ProfileImageComponent workspace={workspace} isFormCreator={isFormCreator} />
                    <WorkspaceHeader isFormCreator={isFormCreator} />
                </div>
                <div className="block md:hidden px-5 lg:px-10">
                    <div className="flex justify-between items-start py-10 gap-6">
                        <ProfileImageComponent workspace={workspace} isFormCreator={isFormCreator} />
                    </div>
                    <WorkspaceHeader isFormCreator={isFormCreator} />
                </div>
                <div className="px-5 lg:px-10 xl:px-20">
                    <FormsAndSubmissionsTabContainer workspace={workspace} workspaceId={workspace.id} showResponseBar={!!authStatus.error} />
                </div>
            </div>
            <WorkspaceFooter workspace={workspace} isCustomDomain={isCustomDomain} />
        </Layout>
    );
}

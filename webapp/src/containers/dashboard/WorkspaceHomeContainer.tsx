import React, { useEffect } from 'react';

import { Divider } from '@mui/material';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import ProfileImageComponent from '@app/components/dashboard/profile-image';
import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import WorkspaceFooter from '@app/components/layout/workspace-footer';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import PublicWorkspaceTitleAndDescription from '@app/components/workspace/public-workspace-title-description';
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
    className?: string;
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
        <Layout showNavbar checkMyDataEnabled className="!p-0 min-h-screen bg-white pb-10 flex flex-col">
            <div className="relative overflow-hidden w-full">
                <BannerImageComponent workspace={workspace} isFormCreator={isFormCreator} />
            </div>
            <div className="md:min-h-[235px] relative bg-brand-100 flex flex-col sm:flex-row pt-6 pb-10 gap-6 px-5 lg:px-10 xl:px-20">
                <ProfileImageComponent className="w-fit sm:w-auto sm:absolute -top-[51px] md:-top-[63px] lg:-top-[73px] rounded overflow-hidden border-4 border-brand-100" workspace={workspace} isFormCreator={isFormCreator} />
                <PublicWorkspaceTitleAndDescription className="pl-0 ml-0 sm:ml-6 sm:pl-32 md:pl-40 lg:pl-[200px]" isFormCreator={isFormCreator} />
            </div>
            <div className="bg-white h-full">
                <FormsAndSubmissionsTabContainer isFormCreator={isFormCreator} workspace={workspace} workspaceId={workspace.id} showResponseBar={!!authStatus.error} />
                <div className="px-5 lg:px-10 xl:px-20">
                    <Divider className="my-10" />
                </div>
                <WorkspaceFooter workspace={workspace} isCustomDomain={isCustomDomain} />
            </div>
        </Layout>
    );
}

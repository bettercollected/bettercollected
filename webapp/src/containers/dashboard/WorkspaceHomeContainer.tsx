import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import { Button } from '@mui/material';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import ProfileImageComponent from '@app/components/dashboard/profile-image';
import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import WorkspaceFooter from '@app/components/layout/workspace-footer';
import { useModal } from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import PublicWorkspaceTitleAndDescription from '@app/components/workspace/public-workspace-title-description';
import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IDashboardContainer {
    isCustomDomain: boolean;
    showProTag?: boolean;
}

export interface BannerImageComponentPropType {
    workspace: WorkspaceDto;
    isFormCreator: boolean;
    className?: string;
}

export default function WorkspaceHomeContainer({ isCustomDomain, showProTag = true }: IDashboardContainer) {
    const authStatus = useGetStatusQuery('status');

    const workspace = useAppSelector(selectWorkspace);

    const { openModal } = useModal();

    if (!workspace) return <FullScreenLoader />;

    const isFormCreator = authStatus.isSuccess && authStatus?.data?.user?.id === workspace?.ownerId;

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${w_name}`;
    };

    return (
        <Layout showNavbar={!isCustomDomain} checkMyDataEnabled className="!p-0 bg-white flex flex-col">
            <div className="relative overflow-hidden w-full">
                <BannerImageComponent workspace={workspace} isFormCreator={false} />
            </div>
            <div className="md:min-h-[157px] relative bg-brand-100 flex flex-col sm:flex-row pt-4 gap-6 px-5 lg:px-10 xl:px-20">
                <ProfileImageComponent className="w-fit sm:w-auto rounded overflow-hidden sm:absolute -top-[51px] md:-top-[63px] lg:-top-[73px] border-4 border-brand-100" workspace={workspace} isFormCreator={false} />
                <div className="flex h-fit w-full gap-10">
                    <PublicWorkspaceTitleAndDescription className="max-w-[400px] ml-0 sm:ml-[152px] md:ml-[184px] lg:ml-[224px]" isFormCreator={false} />
                    <div>
                        <Button onClick={() => openModal('SHARE_VIEW', { url: getWorkspaceUrl(), title: 'your workspace' })} variant="outlined" className="body4 !leading-none !p-2 !text-brand-500 !border-blue-200 hover:!bg-brand-200 capitalize">
                            Share
                        </Button>
                    </div>
                </div>
            </div>
            <div className="bg-white h-full">
                <FormsAndSubmissionsTabContainer isFormCreator={false} workspace={workspace} workspaceId={workspace.id} showResponseBar={!!authStatus.error} />
                <div className="px-5 lg:px-10 xl:px-20">
                    <Divider className="mt-10 mb-6" />
                </div>
                <WorkspaceFooter showProTag={showProTag} workspace={workspace} isCustomDomain={isCustomDomain} />
            </div>
        </Layout>
    );
}

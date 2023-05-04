import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import { Button } from '@mui/material';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
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
    const { isSuccess, isError, data } = useGetStatusQuery('status');

    const workspace = useAppSelector(selectWorkspace);

    const { openModal } = useModal();

    if (!workspace) return <FullScreenLoader />;

    const isFormCreator = isSuccess && data?.user?.id === workspace?.ownerId;

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${w_name}`;
    };

    const handleCheckMyData = () => {
        openModal('LOGIN_VIEW', { isCustomDomain: true });
    };

    return (
        <Layout showNavbar={!isCustomDomain} checkMyDataEnabled className="!p-0 bg-white flex flex-col min-h-screen">
            <div className="relative overflow-hidden w-full">
                <BannerImageComponent workspace={workspace} isFormCreator={false} />
            </div>
            <div className="md:min-h-[157px] relative bg-brand-100 flex flex-col sm:flex-row pt-4 gap-6 px-5 lg:px-10 xl:px-20">
                <ProfileImageComponent className="w-fit sm:w-auto rounded overflow-hidden sm:absolute -top-[51px] md:-top-[63px] lg:-top-[73px] border-4 border-brand-100" workspace={workspace} isFormCreator={false} />
                {isError && (
                    <div className="absolute right-5 lg:right-10 xl:right-20">
                        <Button size="small" variant="contained" className="rounded body4 px-4 py-[13px] !leading-none !normal-case !text-white !bg-brand-500 hover:!bg-brand-600 shadow-none hover:shadow-none" onClick={handleCheckMyData}>
                            Check My Data
                        </Button>
                    </div>
                )}
                <div className="flex h-fit w-full gap-10">
                    <PublicWorkspaceTitleAndDescription className="max-w-[400px] ml-0 sm:ml-[152px] md:ml-[184px] lg:ml-[224px]" isFormCreator={false} />
                    <div className="flex h-fit gap-4 flex-col sm:flex-row">
                        {isSuccess && (
                            <div>
                                <Button onClick={() => openModal('SHARE_VIEW', { url: getWorkspaceUrl(), title: 'your workspace' })} variant="outlined" className="body4 !leading-none !p-2 !text-brand-500 !border-blue-200 hover:!bg-brand-200 capitalize">
                                    Share
                                </Button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
            <div className="bg-white h-full">
                <FormsAndSubmissionsTabContainer isFormCreator={false} workspace={workspace} workspaceId={workspace.id} showResponseBar={!!isError} />
                <div className="px-5 lg:px-10 xl:px-20">
                    <Divider className="mt-10 mb-6" />
                </div>
                <WorkspaceFooter showProTag={showProTag} workspace={workspace} isCustomDomain={isCustomDomain} />
            </div>
        </Layout>
    );
}

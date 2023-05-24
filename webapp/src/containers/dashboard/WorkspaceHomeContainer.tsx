import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
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
import { buttonConstant } from '@app/constants/locales/buttons';
import { workspaceConstant } from '@app/constants/locales/workspace';
import Layout from '@app/layouts/_layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
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
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);

    const { openModal } = useModal();
    const screenSize = useBreakpoint();

    if (!workspace) return <FullScreenLoader />;

    const isFormCreator = isSuccess && data?.user?.id === workspace?.ownerId;

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${w_name}`;
    };

    const handleCheckMyData = () => {
        openModal('LOGIN_VIEW');
    };

    const workspaceOptions = (
        <div className="flex gap-6">
            <Button onClick={() => openModal('SHARE_VIEW', { url: getWorkspaceUrl(), title: t(workspaceConstant.share) })} variant="outlined" className="body4 !leading-none !p-2 !text-brand-500 !border-blue-200 hover:!bg-brand-200 capitalize">
                {t(buttonConstant.share)}
            </Button>
            <AuthAccountMenuDropdown isClientDomain={isCustomDomain ? false : true} menuContent={<EllipsisOption />} showExpandMore={false} className="!text-black-900 !py-0 !px-1" />
        </div>
    );

    return (
        <Layout isCustomDomain={isCustomDomain} isClientDomain showNavbar={!isCustomDomain} hideMenu={!isCustomDomain} className="!p-0 bg-white flex flex-col min-h-screen">
            <div className="relative overflow-hidden w-full">
                <BannerImageComponent workspace={workspace} isFormCreator={false} />
            </div>
            <div className="md:min-h-[157px] relative bg-brand-100 flex flex-col sm:flex-row pt-4 gap-6 px-5 lg:px-10 xl:px-20">
                <ProfileImageComponent className="w-fit sm:w-auto rounded overflow-hidden sm:absolute -top-[51px] md:-top-[63px] lg:-top-[73px] !border-4 border-white sm:!border-brand-100" workspace={workspace} isFormCreator={false} />
                {isError && (
                    <div className="absolute right-5 lg:right-10 xl:right-20">
                        <Button size="small" variant="contained" className="rounded body4 px-4 py-[13px] !leading-none !normal-case !text-white !bg-brand-500 hover:!bg-brand-600 shadow-none hover:shadow-none" onClick={handleCheckMyData}>
                            {t(buttonConstant.checkMyData)}
                        </Button>
                    </div>
                )}
                {['md', 'lg', 'xl', '2xl'].indexOf(screenSize) === -1 && isSuccess && <div className="absolute right-5 lg:right-10 xl:right-20">{workspaceOptions}</div>}
                <div className="flex h-fit w-full gap-10">
                    <PublicWorkspaceTitleAndDescription className="max-w-[800px] ml-0 sm:ml-[152px] md:ml-[184px] lg:ml-[224px]" isFormCreator={false} />
                    {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && isSuccess && <div className="flex h-fit gap-4 flex-col sm:flex-row">{workspaceOptions}</div>}
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

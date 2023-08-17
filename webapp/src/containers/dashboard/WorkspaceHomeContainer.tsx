import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import { Button } from '@mui/material';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import BannerImageComponent from '@app/components/dashboard/banner-image';
import ProfileImageComponent from '@app/components/dashboard/profile-image';
import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import WorkspaceFooter from '@app/components/layout/workspace-footer';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import PublicWorkspaceTitleAndDescription from '@app/components/workspace/public-workspace-title-description';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { UserStatus } from '@app/models/dtos/UserStatus';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/userUtils';

interface IDashboardContainer {
    isCustomDomain: boolean;
    showProTag?: boolean;
    isWorkspacePreview?: boolean;
}

export interface BannerImageComponentPropType {
    workspace: WorkspaceDto;
    isFormCreator: boolean;
    className?: string;
}

export default function WorkspaceHomeContainer({ isCustomDomain, showProTag = true, isWorkspacePreview = false }: IDashboardContainer) {
    const { isSuccess, isError, data } = useGetStatusQuery();
    const { t } = useTranslation();
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const authStatus = useAppSelector(selectAuth);

    const user: UserStatus = authStatus ?? null;
    const { openModal } = useFullScreenModal();
    const screenSize = useBreakpoint();

    if (!workspace) return <FullScreenLoader />;

    const isFormCreator = isSuccess && data?.id === workspace?.ownerId;

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${w_name}`;
    };

    const handleCheckMyData = () => {
        openModal('LOGIN_VIEW');
    };

    const workspaceOptions = isCustomDomain && (
        <AuthAccountMenuDropdown
            isClientDomain={isCustomDomain}
            menuContent={
                <>
                    <AuthAccountProfileImage size={['xs', '2xs'].indexOf(screenSize) === -1 ? 36 : 28} image={user?.profileImage} name={getFullNameFromUser(user) ?? ''} />
                    {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && (
                        <div className="flex flex-col gap-2 text-start justify-center !text-black-700 pr-1">
                            <span className="body6 !leading-none">{getFullNameFromUser(user)?.trim() || user?.email || ''}</span>
                            <span className="body5 !leading-none">{user?.email} </span>
                        </div>
                    )}
                </>
            }
            className="!bg-white !p-2"
        />
    );

    return (
        <>
            {workspace?.bannerImage && (
                <div className={`relative overflow-hidden w-full`}>
                    <BannerImageComponent workspace={workspace} isFormCreator={false} />
                </div>
            )}
            <div
                className={`md:min-h-[157px] ${workspace?.bannerImage ? 'relative ' : ''} ${
                    isWorkspacePreview ? 'px-5 pt-5 lg:px-10 lg:pt-10 xl:pt-20 xl:px-20' : 'pt-3 lg:pt-6  px-5 lg:px-10 xl:px-20'
                } w-full bg-brand-100 flex flex-col sm:flex-row gap-6 `}
            >
                <ProfileImageComponent className={`w-fit sm:w-auto rounded  ${workspace?.bannerImage ? 'sm:absolute -top-[51px] md:-top-[63px] lg:-top-[73px] ' : ''} `} workspace={workspace} isFormCreator={false} />
                {isError && (
                    <div className="absolute right-5 lg:right-10 xl:right-20">
                        <Button size="small" variant="contained" className="rounded body4 px-4 py-[13px] !leading-none !normal-case !text-white !bg-brand-500 hover:!bg-brand-600 shadow-none hover:shadow-none" onClick={handleCheckMyData}>
                            {t(buttonConstant.checkMyData)}
                        </Button>
                    </div>
                )}
                {['md', 'lg', 'xl', '2xl'].indexOf(screenSize) === -1 && isSuccess && <div className="absolute  right-5 lg:right-10 xl:right-20">{workspaceOptions}</div>}
                <div className="flex h-fit w-full justify-between gap-10">
                    <PublicWorkspaceTitleAndDescription className={`max-w-[800px] ${workspace?.bannerImage ? 'ml-0 sm:ml-[152px] md:ml-[184px] lg:ml-[224px]' : ' my-10'} `} isFormCreator={false} />
                    {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && isSuccess && <div className="flex h-fit gap-4 flex-col sm:flex-row">{workspaceOptions}</div>}
                </div>
            </div>
            <div className=" h-full bg-brand-100">
                <FormsAndSubmissionsTabContainer isFormCreator={false} workspace={workspace} workspaceId={workspace.id} showResponseBar={!!isError} />
                <div className="px-5 lg:px-10 xl:px-20">
                    <Divider className="mt-10 mb-6" />
                </div>
                <WorkspaceFooter showProTag={showProTag} workspace={workspace} isCustomDomain={isCustomDomain} />
            </div>
        </>
    );
}

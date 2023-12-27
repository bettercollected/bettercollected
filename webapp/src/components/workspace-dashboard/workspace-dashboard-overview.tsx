import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import EditIcon from '@Components/Common/Icons/Common/Edit';
import PlusIcon from '@Components/Common/Icons/Common/Plus';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import ShareIcon from '@Components/Common/Icons/Common/ShareIcon';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import WorkspaceOptions from '@Components/Common/WorkspaceOptions';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { EyeIcon } from '@app/components/icons/eye-icon';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IWorkspaceDashboardOverviewProps {
    workspace: WorkspaceDto;
}

const WorkspaceDashboardOverview = ({ workspace }: IWorkspaceDashboardOverviewProps) => {
    const { openModal } = useModal();
    const fullScreenModal = useFullScreenModal();
    const isAdmin = useAppSelector(selectIsAdmin);
    const router = useRouter();
    const { t } = useTranslation();
    const language = router?.locale === 'en' ? '' : `${router?.locale}/`;
    const { data } = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });

    const reduxWorkspace = useAppSelector(selectWorkspace);

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        if (workspace.customDomain) {
            return `${protocol}${domain}`;
        }
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${language}${w_name}`;
    };

    const onClickEditButton = () => {
        fullScreenModal.openModal('WORKSPACE_SETTINGS');
    };
    const onClickInviteCollaboratorButton = () => {
        openModal('INVITE_MEMBER');
    };
    const onClickShareWorkspaceButton = () => {
        openModal('SHARE_VIEW', {
            url: getWorkspaceUrl(),
            title: t(workspaceConstant.share)
        });
    };

    return (
        <div className="flex flex-col gap-4">
            <div className="flex lg:flex-row flex-col gap-8 justify-between">
                <div className="flex gap-2 w-full justify-between items-start">
                    <div className="flex flex-col gap-4">
                        <div className="flex  items-center gap-4">
                            <AuthAccountProfileImage name={reduxWorkspace?.title || 'Untitled'} size={72} image={reduxWorkspace?.profileImage} />
                            <div className="flex flex-col gap-2">
                                <div className="h3-new">{reduxWorkspace?.title || 'Untitled'}</div>
                                <div className="p2-new text-black-600 max-w-[200px] md:max-w-[300px] lg:max-w-[409px] line-clamp-2">{reduxWorkspace?.description || ''}</div>
                            </div>
                        </div>
                    </div>
                    <div className="lg:hidden">
                        <WorkspaceOptions workspaceUrl={getWorkspaceUrl()} isAdmin={isAdmin} onClickEdit={onClickEditButton} onShareWorkspace={onClickShareWorkspaceButton} />
                    </div>
                </div>

                {isAdmin && (
                    <div className="flex  lg:flex-col lg:items-end gap-4">
                        <div className="flex flex-col gap-2 lg:items-end">
                            <div className="flex items-center gap-4">
                                <span className="h5-new min-w-[max-content]  text-black-700">
                                    {t('MEMBERS.COLLABORATORS.DEFAULT')} ({data?.length || 1 - 1})
                                </span>
                                <div className="lg:hidden">
                                    <InviteCollaboratorButton onClick={onClickInviteCollaboratorButton} />
                                </div>
                            </div>

                            <div className="flex-1 flex gap-2 max-w-[90vw] overflow-auto lg:overflow-clip lg:!max-w-[330px]">
                                {data?.slice(0, 2)?.map((user) => (
                                    <div key={user.email}>
                                        <AuthAccountProfileImage image={user.profileImage} name={user?.firstName || user?.lastName || user?.email} size={40} variant="circular" />
                                    </div>
                                ))}
                                {data && data?.length > 2 && <div className="bg-gray-200 flex items-center justify-center text-sm  h-10 w-10 rounded-full text-black-800 font-bold">+ {data?.length - 2}</div>}
                            </div>
                        </div>
                    </div>
                )}
            </div>
            <div className=" hidden lg:flex justify-between">
                <div className="flex gap-2">
                    {isAdmin && (
                        <AppButton onClick={onClickEditButton} icon={<SettingsIcon strokeWidth={1} />} variant={ButtonVariant.Ghost}>
                            {t('SETTINGS')}
                        </AppButton>
                    )}
                    <ActiveLink href={getWorkspaceUrl()} target="_blank" referrerPolicy="no-referrer">
                        <AppButton icon={<EyeIcon width={20} height={20} />} variant={ButtonVariant.Ghost}>
                            {t('BUTTON.OPEN_WORKSPACE')}
                        </AppButton>
                    </ActiveLink>
                    <AppButton onClick={onClickShareWorkspaceButton} icon={<ShareIcon strokeWidth={1} height={20} width={20} />} variant={ButtonVariant.Ghost}>
                        {t('SHARE_WORKSPACE')}
                    </AppButton>
                </div>
                {isAdmin && <InviteCollaboratorButton onClick={onClickInviteCollaboratorButton} />}
            </div>
        </div>
    );
};

function InviteCollaboratorButton({ onClick }: { onClick: () => void }) {
    const { t } = useTranslation();
    return (
        <AppButton onClick={onClick} icon={<PlusIcon width={20} height={20} />} variant={ButtonVariant.Ghost} size={ButtonSize.Small}>
            {t('BUTTON.INVITE_COLLABORATOR')}
        </AppButton>
    );
}

export default WorkspaceDashboardOverview;

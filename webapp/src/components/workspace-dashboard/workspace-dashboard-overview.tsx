import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import EditIcon from '@Components/Common/Icons/Edit';
import PlusIcon from '@Components/Common/Icons/Plus';
import ShareIcon from '@Components/Common/Icons/ShareIcon';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import WorkspaceOptions from '@Components/Common/WorkspaceOptions';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { EyeIcon } from '@app/components/icons/eye-icon';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';

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

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${language}${w_name}`;
    };

    const onClickEditButton = () => {
        openModal('EDIT_WORKSPACE_MODAL');
    };
    const onClickOpenLinkButton = () => {
        fullScreenModal.openModal('WORKSPACE_PREVIEW');
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
                            <AuthAccountProfileImage name={workspace?.title || 'Untitled'} size={72} image={workspace?.profileImage} />
                            <div className="flex flex-col gap-2">
                                <div className="h3-new">{workspace?.title || 'Untitled'}</div>
                                <div className="p2-new text-black-600 max-w-[409px] line-clamp-2 max-h-[42px]">{workspace?.description || ''}</div>
                            </div>
                        </div>
                    </div>
                    <div className="lg:hidden">
                        <WorkspaceOptions onClickEdit={onClickEditButton} onOpenLink={onClickOpenLinkButton} onShareWorkspace={onClickShareWorkspaceButton} />
                    </div>
                </div>
                <div className="flex  lg:flex-col lg:items-end gap-4">
                    <div className="flex flex-col gap-2 lg:items-end">
                        <div className="flex items-center gap-4">
                            <span className="h5-new min-w-[max-content]  text-black-700">Collaborators ({data?.length || 1 - 1})</span>
                            <div className="lg:hidden">
                                <InviteCollaboratorButton onClick={onClickInviteCollaboratorButton} />
                            </div>
                        </div>
                        <div>
                            {data?.map((user) => (
                                <div key={user.email}>
                                    <AuthAccountProfileImage image={user.profileImage} name={user?.firstName || user?.lastName || user?.email} size={40} variant="circular" />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
            <div className=" hidden lg:flex justify-between">
                <div className="flex gap-2">
                    <AppButton onClick={onClickEditButton} icon={<EditIcon />} variant={ButtonVariant.Ghost}>
                        Edit
                    </AppButton>
                    <AppButton onClick={onClickOpenLinkButton} icon={<EyeIcon width={20} height={20} />} variant={ButtonVariant.Ghost}>
                        Open Link
                    </AppButton>
                    <AppButton onClick={onClickShareWorkspaceButton} icon={<ShareIcon height={20} width={20} />} variant={ButtonVariant.Ghost}>
                        Share Workspace
                    </AppButton>
                </div>
                <InviteCollaboratorButton onClick={onClickInviteCollaboratorButton} />
            </div>
        </div>
    );
};

function InviteCollaboratorButton({ onClick }: { onClick: () => void }) {
    return (
        <AppButton onClick={onClick} icon={<PlusIcon width={20} height={20} />} variant={ButtonVariant.Ghost} size={ButtonSize.Small}>
            Invite Collaborator
        </AppButton>
    );
}

export default WorkspaceDashboardOverview;

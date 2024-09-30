import React, { useState, useEffect } from 'react';
import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import AuthNavbar from 'src/Components/auth/navbar';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { invitationConstant } from '@app/constants/locales/invitations';
import { toastMessage } from '@app/constants/locales/toast-message';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { UserStatus } from '@app/models/dtos/UserStatus';
import { WorkspaceInvitationDto } from '@app/models/dtos/WorkspaceMembersDto';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import Login from '@app/pages/login/index';
import { useAppSelector } from '@app/store/hooks';
import { useRespondToWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';
import InvalidUserInvitation from '@Components/invitation/sender';
import MainValidUser from '@Components/invitation/MainValidUser';
import Logout from '@Components/Common/Icons/Dashboard/Logout';

import { useModal } from '@app/Components/modal-views/context';
import { useLazyGetStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { useAppDispatch } from '@app/store/hooks';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import ExpiredInvitation from '@Components/invitation/expired';
import Invitations from '@Components/member/invitations';
import LoginComponent from 'src/Components/Login/login-component';

interface Props {
    workspace: WorkspaceDto;
    user: UserStatus | null;
    invitation: WorkspaceInvitationDto | null;
}

const Id: React.FC<Props> = ({ workspace, user, invitation }) => {
    const [trigger, { isLoading }] = useRespondToWorkspaceInvitationMutation();
    const { t } = useTranslation();
    const [rejected, setRejected] = useState<boolean>(false);
    const router = useRouter();
    const { workspaceName } = useAppSelector(selectWorkspace);

    const [logout] = useLogoutMutation();
    const [authTrigger] = useLazyGetStatusQuery();
    const dispatch = useAppDispatch();

    const handleLogout = async () => {
        await logout().then(async () => {
            await authTrigger();
            dispatch(setAuth(initialAuthState));
            router.push(router.asPath);
        });
    };

    if (!user) {
        return <LoginComponent />;
    }

    if (rejected) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center bg-gray-100">
                <NextSeo title={`${t(invitationConstant.title)} | ${workspaceName}`} noindex={true} nofollow={true} />
                <AuthNavbar showHamburgerIcon={false} showPlans={false} />
                <div className="custom-blue-shadow mx-4 flex w-full flex-col items-center rounded-lg border bg-white p-10 shadow-lg md:max-w-[502px]">
                    <img src="/path/to/rejected-request-image.png" alt="Request Rejected" className="mb-6 h-24 w-24 object-cover" />
                    <div className="text-center text-xl font-semibold text-red-600">{t('Request Rejected')}</div>
                </div>
            </div>
        );
    }

    if (!invitation) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center bg-gray-100">
                <NextSeo title={`${t(invitationConstant.title)} | ${workspaceName}`} noindex={true} nofollow={true} />
                <AuthNavbar showHamburgerIcon={false} showPlans={false} />

                <div className="mx-2 mt-10 flex h-[520px] w-full max-w-[420px] flex-col items-center justify-center rounded-xl bg-white p-10 shadow-lg">
                    <img src="/errorr.png" alt="Invitation Not Found" className="h-34 w-34 mb-4 object-cover" />
                    <div className="text-black-800 mb-4 text-center text-2xl font-semibold">{t(workspaceConstant.invitationNotFound)}</div>

                    <p className="mb-4 text-center text-sm text-gray-800">{t(invitationConstant.ensureText)}</p>

                    <p className="cursor-pointer text-sm text-blue-600 hover:underline" onClick={handleLogout}>
                        {t(invitationConstant.switchAccount)}
                    </p>
                </div>
            </div>
        );
    }
    if (invitation && isInvitationExpired(invitation.createdAt, invitation.expiry)) {
        return <ExpiredInvitation />;
    }

    const isInvalidUser = user?.email !== invitation?.email;
    if (isInvalidUser) {
        return (
            <InvalidUserInvitation
                invitation={{
                    email: invitation?.email || '',
                    invitationToken: invitation?.invitationToken || ''
                }}
                workspaceId={workspace.id}
            />
        );
    }

    return <MainValidUser workspace={workspace} user={user} invitation={invitation} />;
};

const isInvitationExpired = (createdAt: string, expiryTimestamp: number) => {
    const currentDate = new Date();
    const invitationExpiryDate = new Date(expiryTimestamp * 1000);

    return currentDate > invitationExpiryDate;
};

export async function getServerSideProps(context: any) {
    const { id } = context.query;
    const config = getServerSideAuthHeaderConfig(context);
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(context)).props;
    let user = null;
    let invitation = null;
    try {
        const userStatus = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, config);
        user = (await userStatus?.json().catch((e: any) => e)) ?? null;
        if (userStatus.status !== 200)
            return {
                props: {
                    ...globalProps
                }
            };
        if (user !== null) {
            const invitation_response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${globalProps.workspace.id}/members/invitations/${id}`, config);
            invitation = await invitation_response?.json();
            if (invitation_response.status !== 200) {
                invitation = null;
            }
        }
    } catch (e) {
        console.log(e);
    }
    return {
        props: {
            ...globalProps,
            user,
            invitation
        }
    };
}

export default Id;

"use client";


import { useTranslation } from 'react-i18next';
import { useParams, useRouter, useSearchParams } from 'next/navigation';

import LoginView from '@app/app/(auth)/_components/login-view';
import AuthNavbar from '@app/components/auth/auth-navbar';
import ExpiredInvitation from '@app/components/invitation/expired';
import { invitationConstant } from '@app/constants/locales/invitations';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { useLazyGetStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { initialAuthState, selectAuth, setAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceInvitationQuery } from '@app/store/workspaces/members-n-invitations-api';
import { useGetWorkspaceByNameQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import MainValidUser from '@Components/invitation/main-valid-user';

const isInvitationExpired = (createdAt: string, expiryTimestamp: number) => {
    const currentDate = new Date();
    const invitationExpiryDate = new Date(expiryTimestamp * 1000);

    return currentDate > invitationExpiryDate;
};

export default function InvitationPage() {
    const params = useParams();
    const searchParams = useSearchParams();
    const id = params?.id as string;
    const invitationWorkspaceName = searchParams?.get('workspace_name');
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const user = useAppSelector(selectAuth);
    const dispatch = useAppDispatch();
    const router = useRouter();

    const [logout] = useLogoutMutation();
    const [authTrigger] = useLazyGetStatusQuery();

    // An invited person has not joined the workspace yet, so the persisted
    // workspace (if any) belongs to a different account/workspace. Resolve
    // the workspace from the signed invitation link instead.
    const {
        data: invitationWorkspace,
        isLoading: isInvitationWorkspaceLoading
    } = useGetWorkspaceByNameQuery(invitationWorkspaceName || '', {
        skip: !invitationWorkspaceName
    });
    const workspaceForInvitation = invitationWorkspaceName
        ? invitationWorkspace
        : workspace;

    const { data: invitation, isLoading: isInvitationLoading } = useGetWorkspaceInvitationQuery(
        {
            workspaceId: workspaceForInvitation?.id || '',
            invitationToken: id
        },
        { skip: !workspaceForInvitation?.id || !id }
    );

    const handleLogout = async () => {
        await logout().then(async () => {
            await authTrigger();
            dispatch(setAuth(initialAuthState));
            window.location.reload();
        });
    };

    if (isInvitationWorkspaceLoading || isInvitationLoading) {
        return null; // Or a loader component
    }

    if (!user?.id) {
        return <LoginView />;
    }

    if (!invitation || !workspaceForInvitation) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center bg-gray-100">
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

    return <MainValidUser workspace={workspaceForInvitation} user={user} invitation={invitation} />;
}

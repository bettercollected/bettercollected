"use client";


import { useTranslation } from 'next-i18next';
import { useParams, useRouter } from 'next/navigation';

import LoginView from '@app/app/(auth)/_components/login-view';
import AuthNavbar from '@app/components/auth/auth-navbar';
import ExpiredInvitation from '@app/components/invitation/expired';
import InvalidUserInvitation from '@app/components/invitation/sender';
import { invitationConstant } from '@app/constants/locales/invitations';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { useLazyGetStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { initialAuthState, selectAuth, setAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceInvitationQuery } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import MainValidUser from '@Components/invitation/main-valid-user';

const isInvitationExpired = (createdAt: string, expiryTimestamp: number) => {
    const currentDate = new Date();
    const invitationExpiryDate = new Date(expiryTimestamp * 1000);

    return currentDate > invitationExpiryDate;
};

export default function InvitationPage() {
    const params = useParams();
    const id = params?.id as string;
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const user = useAppSelector(selectAuth);
    const dispatch = useAppDispatch();
    const router = useRouter();

    const [logout] = useLogoutMutation();
    const [authTrigger] = useLazyGetStatusQuery();

    const { data: invitation, isLoading } = useGetWorkspaceInvitationQuery(
        { workspaceId: workspace?.id, invitationToken: id },
        { skip: !workspace?.id || !id }
    );

    const handleLogout = async () => {
        await logout().then(async () => {
            await authTrigger();
            dispatch(setAuth(initialAuthState));
            window.location.reload();
        });
    };

    if (isLoading) {
        return null; // Or a loader component
    }

    if (!user?.id) {
        return <LoginView />;
    }

    if (!invitation) {
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
}

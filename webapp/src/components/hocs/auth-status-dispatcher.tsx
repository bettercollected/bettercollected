import { UserStatus } from '@app/models/dtos/user-status';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { useGetStatusQuery, useRefreshTokenMutation } from '@app/store/auth/api';
import { resetIfUserChanged } from '@app/store/actions/reset-after-sign-out';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';
import { isAdminDomain } from '@app/utils/domain-utils';
import { isSignedOutError } from '@app/utils/session-answer';
import { useRouter } from 'next/navigation';
import React, { useEffect, useRef, useState } from 'react';

interface IAuthStatusDispatcherProps {
    workspace: WorkspaceDto | null | undefined;
    children: React.ReactNode | React.ReactNode[];
    isCustomDomain?: boolean;
}

export default function AuthStatusDispatcher({ workspace, children }: IAuthStatusDispatcherProps) {
    const router = useRouter();
    const dispatch = useAppDispatch();
    const [is401, setIs401] = useState(false);

    // Only an explicit 401 ends the session here. A server error (a deploy's
    // 502/503, 429) or a network failure leaves the user signed in with their
    // caches (a respondent's half-filled form stays mounted), and the poll
    // asks again on its next round.
    const { data, isLoading, signedOut } = useGetStatusQuery(undefined, {
        pollingInterval: 30000,
        selectFromResult: ({ data, isLoading, isError, error }) => {
            const signedOut = isError && isSignedOutError(error);
            if (data) {
                return { data: { ...data, isLoading }, isLoading, signedOut };
            }
            return { data, isLoading, signedOut };
        },
        skip: is401
    });
    // once, while rendering (React's "adjust state on a change" pattern): the
    // poll is then skipped, so a 401 cannot loop
    if (signedOut && !is401) setIs401(true);

    // The plan claim lives inside the (httpOnly) access token, so an upgrade
    // that happens outside this tab — another session, an admin action, the
    // API — leaves the cookie stale: /auth/status says PRO while every
    // authorized endpoint still sees FREE and 403s. Re-mint the token once
    // per app load and again whenever the server-truth plan changes.
    const [refreshToken] = useRefreshTokenMutation();
    const refreshedOnMountRef = useRef(false);
    const lastPlanRef = useRef<string | undefined>(undefined);
    useEffect(() => {
        if (!data?.id) return;
        const planChanged = lastPlanRef.current !== undefined && lastPlanRef.current !== data.plan;
        lastPlanRef.current = data.plan;
        if (!refreshedOnMountRef.current || planChanged) {
            refreshedOnMountRef.current = true;
            refreshToken();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data?.id, data?.plan]);

    useEffect(() => {
        const currentPath = window.location.pathname;
        const isInvitationPage = currentPath.includes('invitation');
        const isOnAdminDomain = isAdminDomain();

        if (data) {
            const user: UserStatus = { ...data, isLoading: false };
            dispatch(resetIfUserChanged(user.id));
            dispatch(setAuth(user));
        }

        if (is401) {
            // the session ended: the next person at this browser must not see what this user saw
            dispatch(resetIfUserChanged(undefined));
            dispatch(setAuth({ ...initialAuthState, isLoading: false, is401 }));

            // Only redirect if not on invitation page or admin domain
            if (!isInvitationPage && !isOnAdminDomain) {
                router.replace(window.location.href);
            }
        }
        // data?.id: another tab signing in as someone else shows up on the
        // next poll, not only on the next load
    }, [isLoading, is401, workspace, data?.id]);

    return <>{children}</>;
}

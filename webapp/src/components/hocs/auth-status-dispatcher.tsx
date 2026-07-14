import { UserStatus } from '@app/models/dtos/user-status';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { useGetStatusQuery, useRefreshTokenMutation } from '@app/store/auth/api';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';
import { isAdminDomain } from '@app/utils/domain-utils';
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

    const { data, isLoading } = useGetStatusQuery(undefined, {
        pollingInterval: 30000,
        selectFromResult: ({ data, isLoading, isError }) => {
            if (isError) setIs401(true);
            if (data) {
                const isAdmin = workspace?.ownerId === data?.id;
                return { data: { ...data, isAdmin, isLoading }, isLoading };
            }
            return { data, isLoading };
        },
        skip: is401
    });

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
            dispatch(setAuth(user));
        }

        if (is401) {
            dispatch(setAuth({ ...initialAuthState, isLoading: false, is401 }));

            // Only redirect if not on invitation page or admin domain
            if (!isInvitationPage && !isOnAdminDomain) {
                router.replace(window.location.href);
            }
        }

    }, [isLoading, is401, workspace]);

    return <>{children}</>;
}

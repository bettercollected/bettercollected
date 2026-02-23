'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import FullScreenLoader from '@app/Components/ui/fullscreen-loader';
import { useRefreshTokenMutation } from '@app/store/auth/api';

export default function RefreshTokenPage() {
    const [refreshToken] = useRefreshTokenMutation();
    const router = useRouter();

    useEffect(() => {
        const handleRefresh = async () => {
            try {
                await refreshToken().unwrap();
            } catch (error) {
                // Ignore error as we're redirecting to login anyway
            } finally {
                router.replace('/login');
            }
        };
        handleRefresh();
    }, [refreshToken, router]);

    return <FullScreenLoader />;
}

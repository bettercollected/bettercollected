'use client';

import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useRefreshTokenMutation } from '@app/store/auth/api';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

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

import { useEffect } from 'react';

import { useRouter } from 'next/router';

import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useRefreshTokenMutation } from '@app/store/auth/api';

export default function RefreshToken() {
    const [refreshToken, refreshTokenResult] = useRefreshTokenMutation();
    const router = useRouter();
    useEffect(() => {
        (async () => {
            await refreshToken();
            router.replace(`/login`);
        })();
    }, []);
    return <FullScreenLoader />;
}

export function getServerSideProps(_context: any) {
    return {
        props: {}
    };
}

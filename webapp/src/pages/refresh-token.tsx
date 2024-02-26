import { useEffect } from 'react';

import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
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

export async function getServerSideProps({ locale, ..._context }: any) {
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'nl']))
        }
    };
}
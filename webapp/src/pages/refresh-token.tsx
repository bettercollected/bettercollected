import { useEffect } from 'react';

import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useRefreshTokenQuery } from '@app/store/auth/api';

export default function RefreshToken({ workspace }: any) {
    const { data, isError } = useRefreshTokenQuery();
    const router = useRouter();
    useEffect(() => {
        if (isError) {
            toast('Something went wrong.');
        }
        router.push(`/login`);
    }, [data, isError]);
    return <FullScreenLoader />;
}

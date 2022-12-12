import { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import { useDispatch } from 'react-redux';

import { authApi } from '@app/store/auth/api';

export default function AuthHoc({ children }: { children: JSX.Element }) {
    const dispatch = useDispatch();
    const router = useRouter();
    const [authorized, setAuthorized] = useState(false);
    const getStatus = authApi.useLazyGetStatusQuery();

    useEffect(() => {
        console.log('inside use effect');

        //on initial load - run auth check
        authCheck(router.asPath);

        // on route change start-hide page content by setting authorized to false
        const hideContent = () => {
            if (router.asPath === '/' || router.asPath === '/dashboard') {
                setAuthorized(false);
            }
        };

        router.events.on('routeChangeStart', hideContent);

        // on route change complete - run auth check
        router.events.on('routeChangeComplete', authCheck);

        // unsubscribe from events in useEffect return function
        return () => {
            router.events.off('routeChangeStart', hideContent);
            router.events.off('routeChangeComplete', authCheck);
        };
    }, [router.pathname]);

    function authCheck(url: string) {
        //redirect to landing page if accessing a private page and not logged in
        const pathsNotToCheck = ['/privacy_policy', '/'];
        const path = url.split(/[?|#]/)[0];

        const [trigger] = getStatus;
        if (!pathsNotToCheck.includes(path)) {
            //TODO: get status from the api endpoint
            trigger('status')
                .then((data) => {
                    setAuthorized(true);
                    router.push('/mydashboard');
                })
                .catch((e) => {
                    setAuthorized(false);
                });
        } else {
            trigger('status')
                .then((data) => {
                    setAuthorized(true);
                })
                .catch((e) => {
                    router.push('/');
                    setAuthorized(false);
                });
        }

        return authorized ? children : <></>;
    }
}

import { useEffect, useRef } from 'react';

import { useRouter } from 'next/router';

export const usePreserveScroll = () => {
    const router = useRouter();

    const scrollPositions = useRef<{ [url: string]: number }>({});
    const isBack = useRef(false);

    useEffect(() => {
        router.beforePopState(() => {
            isBack.current = true;
            return true;
        });

        const onRouteChangeStart = () => {
            const url = router.pathname;
            scrollPositions.current[url] = window.scrollY;
        };

        const onRouteChangeComplete = (url: any) => {
            if (isBack.current && scrollPositions.current[url]) {
                window.scroll({
                    top: scrollPositions.current[url],
                    behavior: 'auto'
                });
            }

            isBack.current = false;
        };

        router.events.on('routeChangeStart', onRouteChangeStart);
        router.events.on('routeChangeComplete', onRouteChangeComplete);

        return () => {
            router.events.off('routeChangeStart', onRouteChangeStart);
            router.events.off('routeChangeComplete', onRouteChangeComplete);
        };
    }, [router]);
};

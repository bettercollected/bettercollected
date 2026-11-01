'use client';

import { useEffect, useState } from 'react';

import environments from '@app/configs/environments';

/** The API route's path the response read carries (`/workspaces/<id>/submissions/<id>/signatures/<question>`): nothing else is ever fetched with the user's credentials. */
export function signatureImageUrl(path: string | undefined): string | null {
    if (!path || !path.startsWith('/') || path.startsWith('//')) return null;
    return `${environments.API_ENDPOINT_HOST}${path}`;
}

/**
 * A drawn signature's image. The server decrypts it for people who may read the
 * response and never gives out a storage link, so it is fetched with the
 * user's credentials (never cached, never sent on as a referrer) and shown from
 * a blob address, which is revoked when the view goes away. When it cannot be
 * loaded (not allowed, or the file is gone) the text says so instead of a
 * broken image.
 */
export default function SignatureImage({ url, alt, unavailable, className, fallbackClassName }: { url: string; alt: string; unavailable: string; className?: string; fallbackClassName?: string }) {
    const [loaded, setLoaded] = useState<{ url: string; src: string | null; failed: boolean } | null>(null);

    // only an API path is ever fetched with the user's credentials
    const target = signatureImageUrl(url);

    useEffect(() => {
        if (!target) return;
        const controller = new AbortController();
        let objectUrl: string | null = null;
        fetch(target, { credentials: 'include', cache: 'no-store', referrerPolicy: 'no-referrer', signal: controller.signal })
            .then(async (response) => {
                if (!response.ok || !(response.headers.get('content-type') || '').toLowerCase().startsWith('image/png')) throw new Error('not an image');
                const blob = await response.blob();
                if (controller.signal.aborted) return;
                objectUrl = URL.createObjectURL(blob);
                setLoaded({ url, src: objectUrl, failed: false });
            })
            .catch(() => {
                if (!controller.signal.aborted) setLoaded({ url, src: null, failed: true });
            });
        return () => {
            controller.abort();
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [url, target]);

    if (!target) return <span className={fallbackClassName}>{unavailable}</span>;
    if (!loaded || loaded.url !== url) return <span aria-busy="true" className={fallbackClassName} />;
    if (loaded.failed || !loaded.src) return <span className={fallbackClassName}>{unavailable}</span>;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={loaded.src} alt={alt} referrerPolicy="no-referrer" onError={() => setLoaded({ url, src: null, failed: true })} className={className} />;
}

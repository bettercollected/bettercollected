'use client';

import { useEffect } from 'react';

import { useSearchParams } from 'next/navigation';

import { oauthCallbackResult } from '@app/lib/google-oauth-popup';

/**
 * Hands Google's answer to the dashboard window that opened this popup, and
 * closes. Posted only to the dashboard origin: a window on any other origin
 * receives nothing.
 */
export default function GoogleCallbackContent({ dashboardOrigin }: { dashboardOrigin: string | null }) {
    const searchParams = useSearchParams();

    useEffect(() => {
        const parentWindow = window.opener;
        if (parentWindow && dashboardOrigin) {
            parentWindow.postMessage(oauthCallbackResult(searchParams), dashboardOrigin);
        } else {
            console.error('Parent window reference is not available.');
        }
        window.close();
    }, [searchParams, dashboardOrigin]);

    return null;
}

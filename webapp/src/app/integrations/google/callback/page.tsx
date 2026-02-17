'use client';

import { Suspense, useEffect } from 'react';

import { useSearchParams } from 'next/navigation';

function GoogleCallbackContent() {
    const searchParams = useSearchParams();

    useEffect(() => {
        const parentWindow = window.opener;
        if (parentWindow) {
            // Convert searchParams to a plain object to match the previous behavior
            const query: Record<string, string> = {};
            searchParams?.forEach((value, key) => {
                query[key] = value;
            });

            // Send a message to the parent window
            parentWindow.postMessage(query, '*');
        } else {
            console.error('Parent window reference is not available.');
        }
        window.close();
    }, [searchParams]);

    return null;
}

export default function GoogleCallbackPage() {
    return (
        <Suspense fallback={null}>
            <GoogleCallbackContent />
        </Suspense>
    );
}

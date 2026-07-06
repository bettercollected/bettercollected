'use client';

import { useEffect } from 'react';

/**
 * Error boundary for the form editor route.
 *
 * The most common real-world failure here is a stale tab after a deploy (or a
 * dev-server rebuild): the page requests a JS chunk whose hash no longer
 * exists → ChunkLoadError. A full reload always fixes that, so offer it
 * first-class instead of a blank screen or a raw overlay.
 */
export default function EditPageError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
    const isStaleChunk = /ChunkLoadError|Loading chunk|failed to fetch dynamically imported module/i.test(error?.message || '') || /ChunkLoadError/i.test(error?.name || '');

    useEffect(() => {
        // eslint-disable-next-line no-console
        console.error('Form editor crashed:', error);
    }, [error]);

    return (
        <div className="flex h-screen w-full flex-col items-center justify-center gap-3 bg-white px-6 text-center">
            <div className="text-black-900 text-lg font-semibold">{isStaleChunk ? 'The editor was updated' : 'The editor hit a problem'}</div>
            <p className="text-black-600 max-w-md text-sm">
                {isStaleChunk
                    ? 'This tab was open while a newer version was published. Reload to pick up the latest editor — your form is saved on the server.'
                    : 'Your form is saved on the server — nothing is lost. Try again, or reload the editor.'}
            </p>
            {!isStaleChunk && error?.message && <code className="text-black-500 max-w-lg truncate rounded bg-black-100 px-2 py-1 text-xs">{error.message}</code>}
            <div className="mt-2 flex items-center gap-3">
                {!isStaleChunk && (
                    <button onClick={reset} className="border-black-300 text-black-700 hover:border-brand-500 rounded-md border px-4 py-2 text-sm font-medium">
                        Try again
                    </button>
                )}
                <button onClick={() => window.location.reload()} className="bg-brand-500 hover:bg-brand-600 rounded-md px-4 py-2 text-sm font-medium text-white">
                    Reload editor
                </button>
            </div>
        </div>
    );
}

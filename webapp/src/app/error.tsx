'use client';

import { useEffect } from 'react';

import BetterCollectedLogo from '@Components/icons/bettercollected-logo';

/**
 * Branded 500 boundary for the whole app (renders inside the root layout).
 *
 * Like the editor boundary, the most common real-world cause is a stale tab
 * after a deploy requesting a JS chunk whose hash no longer exists
 * (ChunkLoadError) — a full reload fixes that, so offer it first-class. Any
 * deeper route that wants a more specific message can add its own error.tsx.
 */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
    const isStaleChunk =
        /ChunkLoadError|Loading chunk|failed to fetch dynamically imported module/i.test(error?.message || '') || /ChunkLoadError/i.test(error?.name || '');

    useEffect(() => {
        // eslint-disable-next-line no-console
        console.error('Application error:', error);
    }, [error]);

    return (
        <main className="flex min-h-screen w-full flex-col items-center justify-center gap-6 bg-white px-6 py-16 text-center">
            <BetterCollectedLogo className="h-[19px]" />

            <div className="flex flex-col items-center gap-3">
                <span className="text-brand-500 text-sm font-semibold uppercase tracking-wide">{isStaleChunk ? 'Update available' : 'Something went wrong'}</span>
                <h1 className="text-black-900 text-2xl font-semibold sm:text-3xl">{isStaleChunk ? 'This tab is out of date' : 'We hit an unexpected problem'}</h1>
                <p className="text-black-600 max-w-md text-sm leading-relaxed sm:text-base">
                    {isStaleChunk
                        ? 'A newer version was published while this tab was open. Reload to pick up the latest — your work is saved on the server.'
                        : 'This one is on us. Your data is safe. Try again, and if it keeps happening, reload the page.'}
                </p>
                {!isStaleChunk && error?.digest && <code className="text-black-500 bg-black-100 rounded px-2 py-1 text-xs">Reference: {error.digest}</code>}
            </div>

            <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
                {!isStaleChunk && (
                    <button onClick={reset} className="border-black-300 text-black-700 hover:border-brand-500 rounded-md border px-5 py-2.5 text-sm font-medium transition-colors">
                        Try again
                    </button>
                )}
                <button onClick={() => window.location.reload()} className="bg-brand-500 hover:bg-brand-600 rounded-md px-5 py-2.5 text-sm font-medium text-white transition-colors">
                    {isStaleChunk ? 'Reload page' : 'Reload'}
                </button>
            </div>
        </main>
    );
}

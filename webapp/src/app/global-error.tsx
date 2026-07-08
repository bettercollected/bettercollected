'use client';

import { useEffect } from 'react';

import BetterCollectedLogo from '@Components/icons/bettercollected-logo';

/**
 * Last-resort boundary: catches errors thrown in the root layout itself, so it
 * REPLACES the layout and renders its own <html>/<body>. That means no
 * globals.css and no Public Sans here — everything is inlined so the page
 * survives even when the stylesheet or font pipeline is what failed. Kept
 * deliberately minimal; the in-layout error.tsx handles the common cases with
 * the full design system.
 */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
    useEffect(() => {
        // eslint-disable-next-line no-console
        console.error('Fatal application error:', error);
    }, [error]);

    return (
        <html lang="en">
            <body
                style={{
                    margin: 0,
                    minHeight: '100vh',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '20px',
                    padding: '64px 24px',
                    textAlign: 'center',
                    background: '#ffffff',
                    color: '#101826',
                    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
                }}
            >
                <BetterCollectedLogo style={{ height: 19 }} />
                <h1 style={{ margin: 0, fontSize: 26, fontWeight: 600 }}>We hit an unexpected problem</h1>
                <p style={{ margin: 0, maxWidth: 420, fontSize: 15, lineHeight: 1.6, color: '#657085' }}>
                    This one is on us. Your data is safe. Reload the page, and if it keeps happening, please try again in a moment.
                </p>
                {error?.digest && <code style={{ fontSize: 12, color: '#657085', background: '#F6F8FC', padding: '4px 8px', borderRadius: 4 }}>Reference: {error.digest}</code>}
                <button
                    onClick={reset}
                    style={{
                        marginTop: 8,
                        cursor: 'pointer',
                        border: 'none',
                        borderRadius: 6,
                        padding: '10px 20px',
                        fontSize: 14,
                        fontWeight: 500,
                        color: '#ffffff',
                        background: '#2456CC'
                    }}
                >
                    Reload
                </button>
            </body>
        </html>
    );
}

'use client';

import React, { useEffect, useRef } from 'react';

import { usePathname } from 'next/navigation';

/** How long to wait for a page that loads its content before it shows a heading (the Automations cards). */
const WAIT_FOR_HEADING_MS = 3000;

/**
 * Settings is five pages (`/settings/access`, `/availability`, `/experience`, `/automations`, `/advanced`) chosen in
 * the form's side menu. When the viewer moves from one to another, focus goes to the new page's heading (h2), so a
 * keyboard or screen reader user lands on what they chose, not on the link they left. Not on the first load (the page
 * then starts where it always did), and not when only the query changes (an open automation sheet).
 */
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const previous = useRef<string | null>(null);

    useEffect(() => {
        const before = previous.current;
        previous.current = pathname;
        if (before === null || before === pathname) return;

        const main = document.getElementById('form-main');
        const focusHeading = () => {
            const heading = main?.querySelector<HTMLElement>('h2');
            heading?.focus({ preventScroll: true });
            return !!heading;
        };
        let stop = () => {};
        let timer: ReturnType<typeof setTimeout> | undefined;
        let frame = requestAnimationFrame(() => {
            frame = 0;
            if (focusHeading() || !main) return;
            // the page is still loading what it shows: take the heading when it appears
            const observer = new MutationObserver(() => {
                if (focusHeading()) observer.disconnect();
            });
            observer.observe(main, { childList: true, subtree: true });
            stop = () => observer.disconnect();
            timer = setTimeout(stop, WAIT_FOR_HEADING_MS);
        });
        return () => {
            if (frame) cancelAnimationFrame(frame);
            stop();
            clearTimeout(timer);
        };
    }, [pathname]);

    return <>{children}</>;
}

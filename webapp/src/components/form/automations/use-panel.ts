'use client';

import { useCallback, useEffect, useRef } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { PANEL_PARAM, Panel, parsePanel, withPanel } from './panels';

/**
 * The open side sheet of the Automations cards, kept in the URL (`?panel=`).
 * Opening adds a history entry, so Back closes the sheet; closing a sheet that
 * this page opened goes back, so the history does not grow with every open and
 * close. A sheet opened by a link has no entry of ours: closing replaces the URL.
 */
export function usePanel() {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const requested = searchParams?.get(PANEL_PARAM) ?? null;
    const panel = parsePanel(requested);
    const openedHere = useRef(false);

    // The sheet is gone (closed, or Back): the next one starts fresh.
    useEffect(() => {
        if (!requested) openedHere.current = false;
    }, [requested]);

    const open = useCallback(
        (next: Panel) => {
            openedHere.current = true;
            router.push(`${pathname}${withPanel(searchParams?.toString() ?? '', next)}`, { scroll: false });
        },
        [router, pathname, searchParams]
    );

    const close = useCallback(() => {
        if (openedHere.current) {
            openedHere.current = false;
            router.back();
        } else {
            router.replace(`${pathname}${withPanel(searchParams?.toString() ?? '', null)}`, { scroll: false });
        }
    }, [router, pathname, searchParams]);

    return { panel, open, close };
}

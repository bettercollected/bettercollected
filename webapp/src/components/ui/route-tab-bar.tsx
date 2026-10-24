'use client';

import React, { useEffect, useRef } from 'react';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { isTabActive } from '@app/lib/workspace-sections';
import { cn } from '@app/shadcn/util/lib';

export interface RouteTab {
    key: string;
    label: React.ReactNode;
    href: string;
    icon?: React.ReactNode;
    /** Active on this exact path only (its href prefixes the other tabs). */
    exact?: boolean;
}

interface RouteTabBarProps {
    /** Names the region for screen readers, e.g. "AI sections". */
    ariaLabel: string;
    tabs: Array<RouteTab>;
    className?: string;
}

/**
 * Tabs that are pages: each tab is a link to its own route, so it can be
 * bookmarked and survives a reload. For panels inside one page use the
 * shadcn Tabs instead.
 *
 * A nav of links, the current one marked aria-current="page" (no
 * role="tablist": these navigate). The active tab is shown by weight and the
 * underline, not colour alone. At narrow widths the bar scrolls sideways in
 * its own region and keeps the active tab in view. With fewer than two tabs
 * there is nothing to choose between, so nothing is rendered.
 */
export default function RouteTabBar({ ariaLabel, tabs, className }: RouteTabBarProps) {
    const pathname = usePathname();
    const listRef = useRef<HTMLUListElement>(null);
    const activeHref = tabs.find((tab) => isTabActive(pathname, tab))?.href;

    useEffect(() => {
        const list = listRef.current;
        const active = list?.querySelector<HTMLElement>('[aria-current="page"]');
        if (!list || !active) return;
        // Horizontal only: scrollIntoView would also move the page.
        const left = active.offsetLeft - list.offsetLeft;
        if (left < list.scrollLeft || left + active.offsetWidth > list.scrollLeft + list.clientWidth) {
            list.scrollLeft = Math.max(0, left - (list.clientWidth - active.offsetWidth) / 2);
        }
    }, [activeHref]);

    if (tabs.length < 2) return null;

    return (
        <nav aria-label={ariaLabel} className={cn('mb-[38px] max-w-full min-w-0', className)}>
            <ul ref={listRef} className="scrollbar-hide m-0 flex list-none gap-1 overflow-x-auto overscroll-x-contain border-b border-black-400 p-0">
                {tabs.map((tab) => {
                    const active = tab.href === activeHref;
                    return (
                        <li key={tab.key} className="shrink-0">
                            <Link
                                href={tab.href}
                                aria-current={active ? 'page' : undefined}
                                className={cn(
                                    'mb-[-1px] flex min-h-[44px] items-center gap-2 rounded-t-md border-b-2 px-4 text-sm whitespace-nowrap transition-colors',
                                    // The app-wide focus outline (tailwind.css), drawn inside: the scroll region would clip it outside.
                                    'focus-visible:outline-offset-[-2px]!',
                                    active ? 'border-brand-500 font-semibold text-brand-500' : 'border-transparent font-medium text-black-600 hover:border-black-400 hover:text-black-800'
                                )}
                            >
                                {tab.icon}
                                {/* The bold copy reserves the active width, so tabs don't shift when the weight changes. */}
                                <span className="grid">
                                    <span aria-hidden="true" className="invisible col-start-1 row-start-1 h-0 font-semibold">
                                        {tab.label}
                                    </span>
                                    <span className="col-start-1 row-start-1">{tab.label}</span>
                                </span>
                            </Link>
                        </li>
                    );
                })}
            </ul>
        </nav>
    );
}

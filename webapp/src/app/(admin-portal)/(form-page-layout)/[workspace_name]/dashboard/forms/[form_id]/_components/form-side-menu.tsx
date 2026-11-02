'use client';

import React, { useState, useSyncExternalStore } from 'react';

import Link from 'next/link';

import { Check, ChevronDown, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@app/shadcn/components/ui/sheet';
import { cn } from '@app/shadcn/util/lib';

import { FormNavItem, currentItem } from './form-nav';

/* ------------------------------------------------- collapsed or expanded */

const STORAGE_KEY = 'form-rail-collapsed';

/** What the viewer chose; `auto` until they choose: collapsed below 1280 px, expanded from there. */
type RailMode = 'auto' | 'collapsed' | 'expanded';

function readMode(): RailMode {
    try {
        const stored = window.localStorage.getItem(STORAGE_KEY);
        return stored === '1' ? 'collapsed' : stored === '0' ? 'expanded' : 'auto';
    } catch {
        // storage blocked (private window, cleared site data): the default holds
        return 'auto';
    }
}

function writeMode(mode: Exclude<RailMode, 'auto'>) {
    try {
        window.localStorage.setItem(STORAGE_KEY, mode === 'collapsed' ? '1' : '0');
    } catch {
        /* the choice then lasts until the page is left */
    }
}

const subscribeToStorage = (onChange: () => void) => {
    window.addEventListener('storage', onChange);
    return () => window.removeEventListener('storage', onChange);
};

const WIDE = '(min-width: 1280px)';
const subscribeToWidth = (onChange: () => void) => {
    const query = window.matchMedia?.(WIDE);
    query?.addEventListener?.('change', onChange);
    return () => query?.removeEventListener?.('change', onChange);
};
const isWide = () => !!window.matchMedia?.(WIDE)?.matches;

/**
 * The side menu's state. How it looks follows `mode` in CSS (so the first paint is right at every width, with no
 * flash); `collapsed` is the same fact for `aria-expanded` and the button's name, known once the page is mounted.
 */
export function useRail() {
    const stored = useSyncExternalStore(subscribeToStorage, readMode, () => 'auto' as RailMode);
    const wide = useSyncExternalStore(subscribeToWidth, isWide, () => false);
    // what was chosen on this page, kept even when storage is blocked
    const [chosen, setChosen] = useState<Exclude<RailMode, 'auto'> | null>(null);

    const mode: RailMode = chosen ?? stored;
    const collapsed = mode === 'auto' ? !wide : mode === 'collapsed';
    const toggle = () => {
        const next = collapsed ? 'expanded' : 'collapsed';
        setChosen(next);
        writeMode(next);
    };
    return { mode, collapsed, toggle };
}

/** One class string per mode: `auto` is the collapsed look below `xl`, the expanded one from `xl`. */
const byMode = (mode: RailMode, classes: { collapsed: string; expanded: string; auto: string }) => classes[mode];

/* ------------------------------------------------------------------ rail */

function RailLink({ item, mode, collapsed, child }: { item: FormNavItem; mode: RailMode; collapsed: boolean; child?: boolean }) {
    const Icon = item.icon;
    const isCurrent = item.active && !item.children?.some((c) => c.active);
    return (
        <Link
            href={item.href}
            aria-current={isCurrent ? 'page' : undefined}
            title={collapsed ? item.label : undefined}
            className={cn(
                'flex min-h-10 items-center gap-2.5 rounded px-2.5 text-sm',
                byMode(mode, { collapsed: 'justify-center px-0', expanded: '', auto: 'justify-center px-0 xl:justify-start xl:px-2.5' }),
                child && byMode(mode, { collapsed: '', expanded: 'pl-9', auto: 'xl:pl-9' }),
                isCurrent ? 'bg-brand-100 font-semibold text-brand-700' : item.active ? 'font-semibold text-black-900' : 'font-medium text-black-700 hover:bg-black-200 hover:text-black-900'
            )}
        >
            <Icon aria-hidden="true" className={cn('h-[18px] w-[18px] shrink-0', child && byMode(mode, { collapsed: '', expanded: 'hidden', auto: 'xl:hidden' }))} />
            <span className={cn('min-w-0 flex-1 truncate', byMode(mode, { collapsed: 'sr-only', expanded: '', auto: 'sr-only xl:not-sr-only' }))}>{item.label}</span>
            {typeof item.count === 'number' && (
                <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium tabular-nums', isCurrent ? 'bg-white text-brand-700' : 'bg-black-200 text-black-700', byMode(mode, { collapsed: 'hidden', expanded: '', auto: 'hidden xl:inline' }))}>
                    {item.count}
                </span>
            )}
        </Link>
    );
}

/** The sections of the form down the side of the page (from `md`); icons only when collapsed. */
export function FormRail({ items }: { items: FormNavItem[] }) {
    const { t } = useTranslation();
    const { mode, collapsed, toggle } = useRail();
    const label = collapsed ? t('FORM_NAV.EXPAND') : t('FORM_NAV.COLLAPSE');
    return (
        <div
            id="form-rail"
            className={cn(
                'sticky top-14 hidden h-[calc(100dvh-3.5rem)] shrink-0 flex-col self-start border-r border-black-400 bg-white transition-[width] duration-150 motion-reduce:transition-none md:flex',
                byMode(mode, { collapsed: 'w-14', expanded: 'w-60', auto: 'w-14 xl:w-60' })
            )}
        >
            <nav aria-label={t('FORM_NAV.SECTIONS')} className="flex-1 overflow-y-auto p-2">
                <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
                    {items.map((item) => (
                        <li key={item.key}>
                            <RailLink item={item} mode={mode} collapsed={collapsed} />
                            {item.children && (!item.opensInPlace || item.active) && (
                                <ul className="m-0 mt-0.5 flex list-none flex-col gap-0.5 p-0">
                                    {item.children.map((child) => (
                                        <li key={child.key}>
                                            <RailLink item={child} mode={mode} collapsed={collapsed} child />
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </li>
                    ))}
                </ul>
            </nav>
            <div className="border-t border-black-300 p-2">
                <button
                    type="button"
                    aria-expanded={!collapsed}
                    aria-controls="form-rail"
                    aria-label={label}
                    title={collapsed ? label : undefined}
                    onClick={toggle}
                    className={cn(
                        'flex h-10 w-full items-center gap-2.5 rounded px-2.5 text-sm text-black-600 hover:bg-black-200 hover:text-black-900',
                        byMode(mode, { collapsed: 'justify-center px-0', expanded: '', auto: 'justify-center px-0 xl:justify-start xl:px-2.5' })
                    )}
                >
                    {collapsed ? <ChevronsRight aria-hidden="true" className="h-[18px] w-[18px] shrink-0" /> : <ChevronsLeft aria-hidden="true" className="h-[18px] w-[18px] shrink-0" />}
                    <span className={cn(byMode(mode, { collapsed: 'sr-only', expanded: '', auto: 'sr-only xl:not-sr-only' }))} aria-hidden="true">
                        {label}
                    </span>
                </button>
            </div>
        </div>
    );
}

/* ----------------------------------------------------------------- phone */

function SheetLink({ item, child, onNavigate }: { item: FormNavItem; child?: boolean; onNavigate: () => void }) {
    const Icon = item.icon;
    const isCurrent = item.active && !item.children?.some((c) => c.active);
    return (
        <Link
            href={item.href}
            onClick={onNavigate}
            aria-current={isCurrent ? 'page' : undefined}
            className={cn('flex min-h-11 items-center gap-3 rounded px-3 text-[15px]', child && 'pl-10', isCurrent ? 'bg-brand-100 font-semibold text-brand-700' : item.active ? 'font-semibold text-black-900' : 'text-black-800 hover:bg-black-200')}
        >
            {!child && <Icon aria-hidden="true" className="h-[18px] w-[18px] shrink-0" />}
            <span className="min-w-0 flex-1 truncate">{item.label}</span>
            {typeof item.count === 'number' && <span className="rounded-full bg-black-200 px-2 py-0.5 text-xs font-medium text-black-700 tabular-nums">{item.count}</span>}
            {isCurrent && <Check aria-hidden="true" className="h-4 w-4 shrink-0 text-brand-600" />}
        </Link>
    );
}

/**
 * On a phone the sections do not fit beside the page: a row under the bar names the current one and opens a sheet
 * from the bottom that lists them all. The sheet traps focus, closes on Escape and returns focus to the row.
 */
export function SectionSwitcher({ items }: { items: FormNavItem[] }) {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    const current = currentItem(items);
    const parent = items.find((item) => item.children?.some((c) => c.active));
    const name = parent && current ? `${parent.label} · ${current.label}` : (current?.label ?? '');
    return (
        <div className="flex min-h-11 items-center border-b border-black-300 bg-white px-3 md:hidden">
            <Sheet open={open} onOpenChange={setOpen}>
                <SheetTrigger asChild>
                    <button type="button" aria-label={t('FORM_NAV.SWITCH_OPEN', { name })} className="flex h-11 min-w-0 flex-1 items-center gap-2 text-left text-sm font-semibold text-black-900">
                        <span className="truncate">{name}</span>
                        <ChevronDown aria-hidden="true" className="h-[18px] w-[18px] shrink-0" />
                    </button>
                </SheetTrigger>
                <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto rounded-t-lg p-0 pb-4">
                    <SheetHeader className="h-[4.25rem] justify-center border-b border-black-300 px-4 pr-16">
                        <SheetTitle>{t('FORM_NAV.GO_TO')}</SheetTitle>
                    </SheetHeader>
                    <nav aria-label={t('FORM_NAV.GO_TO')} className="px-2 pt-2">
                        <ul className="m-0 list-none p-0">
                            {items.map((item) => (
                                <li key={item.key}>
                                    <SheetLink item={item} onNavigate={() => setOpen(false)} />
                                    {item.children && (
                                        <ul className="m-0 list-none p-0">
                                            {item.children.map((child) => (
                                                <li key={child.key}>
                                                    <SheetLink item={child} child onNavigate={() => setOpen(false)} />
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </li>
                            ))}
                        </ul>
                    </nav>
                </SheetContent>
            </Sheet>
        </div>
    );
}

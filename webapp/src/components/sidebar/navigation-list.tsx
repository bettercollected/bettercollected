import { useEffect } from 'react';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { CountBadge } from '@app/components/ui/count-badge';
import { isNavItemActive } from '@app/lib/nav-items';
import { INavbarItem } from '@app/models/props/navbar';
import { cn } from '@app/shadcn/util/lib';
import { isValidRelativeURL } from '@app/utils/url-utils';

interface INavigationListProps {
    navigationList: Array<INavbarItem>;
    className?: string;
    sx?: any; // kept for compatibility but ignored or mapped to style
}

export default function NavigationList({ navigationList, className = '', sx = {} }: INavigationListProps) {
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        navigationList?.forEach((lst) => {
            if (isValidRelativeURL(lst.url)) router.prefetch(lst.url);
        });
    }, [navigationList, router]);

    return (
        <ul className={cn("flex flex-col gap-1 p-0 m-0 list-none", className)}>
            {navigationList?.map((element) => {
                // Prefix match (lib/nav-items.ts): nested routes such as
                // /members/collaborators or /ai/memory keep their item selected.
                const active = isNavItemActive(pathname, element);
                // The box the row always had (the old <li> and its inner row, now one element): a link or a button is
                // focusable and announced, and carries the same padding, radius, colours and hover.
                const rowClass = cn(
                    "flex w-full items-center px-4 py-2 cursor-pointer rounded-lg text-sm transition-colors",
                    active ? "bg-brand-tint text-link font-medium" : "text-copy hover:bg-sunken hover:text-ink"
                );
                const row = (
                    <>
                        {element.icon && (
                            <span className={cn("mr-3 flex h-5 w-5 items-center justify-center", active ? "text-link" : "text-ink-muted")}>
                                {element?.icon}
                            </span>
                        )}
                        <span className="min-w-0 flex-1 truncate">{element.name}</span>
                        {element.badge && element.badge.count > 0 && <CountBadge count={element.badge.count} label={element.badge.label} className="ml-2" />}
                    </>
                );
                // A link only where the url is a page of its own (a relative url, as before): Enter follows it, it opens
                // in a new tab, and the current one is announced. An item that acts in place (opens a view or a dialog
                // on this page) is a button even when it has a url.
                if (isValidRelativeURL(element.url) && !element.opensInPlace) {
                    return (
                        <li key={element.key}>
                            <Link
                                href={element.url}
                                // prefetched once, in the effect above, as before
                                prefetch={false}
                                aria-current={active ? 'page' : undefined}
                                className={rowClass}
                                onClick={(event) => {
                                    // An item with its own action keeps it on a plain click; a new-tab or new-window
                                    // click goes to the url.
                                    if (!element.onClick || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                                    event.preventDefault();
                                    element.onClick();
                                }}
                            >
                                {row}
                            </Link>
                        </li>
                    );
                }
                if (element.onClick) {
                    return (
                        <li key={element.key}>
                            <button type="button" aria-current={active ? 'true' : undefined} className={cn(rowClass, "text-start")} onClick={element.onClick}>
                                {row}
                            </button>
                        </li>
                    );
                }
                return (
                    <li key={element.key}>
                        <div className={rowClass}>{row}</div>
                    </li>
                );
            })}
        </ul>
    );
}

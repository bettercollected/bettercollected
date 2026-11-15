import { useEffect } from 'react';

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
                return (
                    <li key={element.key}
                        className={cn(
                            "cursor-pointer rounded-lg text-sm transition-colors",
                            active ? "bg-brand-tint text-link font-medium" : "text-copy hover:bg-sunken hover:text-ink"
                        )}
                        onClick={() => {
                            if (element.onClick) {
                                element.onClick();
                            } else if (isValidRelativeURL(element.url)) {
                                router.push(element.url);
                            }
                        }}
                    >
                        <div className="flex items-center px-4 py-2 w-full">
                            {element.icon && (
                                <span className={cn("mr-3 flex h-5 w-5 items-center justify-center", active ? "text-link" : "text-ink-muted")}>
                                    {element?.icon}
                                </span>
                            )}
                            <span className="min-w-0 flex-1 truncate">{element.name}</span>
                            {element.badge && element.badge.count > 0 && <CountBadge count={element.badge.count} label={element.badge.label} className="ml-2" />}
                        </div>
                    </li>
                );
            })}
        </ul>
    );
}

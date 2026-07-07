import { useEffect } from 'react';

import { usePathname, useRouter } from 'next/navigation';

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
                // Prefix match, not equality — nested routes (e.g.
                // /responders-groups/all-responders, /members/collaborators)
                // left the whole sidebar with nothing selected. Items whose URL
                // prefixes everything (the dashboard root) opt into exact match;
                // items whose active state isn't a route (Site settings is a
                // view on the dashboard root) pass it in directly.
                const active = element.isActive ?? (pathname === element.url || (!element.exactMatch && pathname?.startsWith(element.url + '/')));
                return (
                    <li key={element.key}
                        className={cn(
                            "cursor-pointer rounded-lg text-sm transition-colors",
                            active ? "bg-[#E9EFFC] text-[#2456CC] font-medium" : "text-black-700 hover:bg-black-100 hover:text-black-900"
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
                                <span className={cn("mr-3 flex h-5 w-5 items-center justify-center", active ? "text-[#2456CC]" : "text-black-600")}>
                                    {element?.icon}
                                </span>
                            )}
                            <span className="truncate">{element.name}</span>
                        </div>
                    </li>
                );
            })}
        </ul>
    );
}

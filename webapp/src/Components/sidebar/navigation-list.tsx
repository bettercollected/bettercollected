import React, { useEffect } from 'react';

import { usePathname, useRouter } from 'next/navigation';

import { INavbarItem } from '@app/models/props/navbar';
import { isValidRelativeURL } from '@app/utils/urlUtils';
import { cn } from '@app/shadcn/util/lib';

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
                const active = element.url == pathname;
                return (
                    <li key={element.key}
                        className={cn(
                            "cursor-pointer rounded-lg text-sm transition-colors",
                            active ? "bg-slate-100 text-slate-900 font-medium" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
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
                                <span className={cn("mr-3 flex h-5 w-5 items-center justify-center", active ? "text-slate-900" : "text-slate-500")}>
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

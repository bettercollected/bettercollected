'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';
import { useTranslation } from 'react-i18next';

import MembersIcon from '@Components/icons/members';
import { members } from '@app/constants/locales/members';

export default function MembersLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: { workspace_name: string }
}) {
    const { t } = useTranslation();
    const pathname = usePathname();

    const tabs = [
        {
            icon: <MembersIcon />,
            title: t(members.collaborators.default),
            path: 'collaborators'
        },
        {
            icon: <MembersIcon />,
            title: t(members.pendingRequests.default),
            path: 'pending-requests'
        }
    ];

    // No page h1 here — the sticky top bar already titles the page, and the
    // section below ("Collaborators (N)") carries the specifics. Selection is
    // the trust-blue underline used across the app.
    return (
        <div className="flex flex-col">
            <div className="mb-[38px]">
                <div className="border-black-300 flex space-x-1 overflow-x-auto border-b pb-0">
                    {tabs.map((tab) => {
                        const isActive = pathname?.includes(`/${tab.path}`);
                        return (
                            <Link
                                key={tab.path}
                                href={`/${params?.workspace_name}/dashboard/members/${tab.path}`}
                                className={cn(
                                    'mb-[-1px] flex cursor-pointer items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                                    isActive
                                        ? 'border-[#2456CC] text-[#2456CC]'
                                        : 'text-black-600 hover:text-black-800 border-transparent'
                                )}
                            >
                                {tab.icon}
                                {tab.title}
                            </Link>
                        );
                    })}
                </div>
            </div>
            <div>{children}</div>
        </div>
    );
}

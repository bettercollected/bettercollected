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

    return (
        <div className="flex flex-col">
            <div className="flex justify-between">
                <div className="h4">{t(members.default)}</div>
            </div>
            <div className="mb-[38px] mt-[24px]">
                <div className="flex space-x-1 border-b border-gray-200 overflow-x-auto pb-0">
                    {tabs.map((tab) => {
                        const isActive = pathname?.includes(`/${tab.path}`);
                        return (
                            <Link
                                key={tab.path}
                                href={`/${params?.workspace_name}/dashboard/members/${tab.path}`}
                                className={cn(
                                    'flex items-center gap-2 px-4 py-2 text-sm font-medium mb-[-1px] cursor-pointer hover:bg-black-200 hover:rounded whitespace-nowrap',
                                    isActive
                                        ? 'border-b-2 border-black-900 text-black-900'
                                        : 'text-gray-500 hover:text-gray-700 hover:border-gray-300'
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

'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import cn from 'classnames';
import { useTranslation } from 'react-i18next';

import ResponderIcon from '@app/views/atoms/Icons/Responder';
import UserMore from '@app/views/atoms/Icons/UserMore';
import { groupConstant } from '@app/constants/locales/group';
import { workspaceConstant } from '@app/constants/locales/workspace';

interface RespondersGroupsLayoutClientProps {
    children: React.ReactNode;
    workspaceName: string;
}

export default function RespondersGroupsLayoutClient({ children, workspaceName }: RespondersGroupsLayoutClientProps) {
    const { t } = useTranslation();
    const pathname = usePathname();

    const tabs = [
        {
            icon: <ResponderIcon className="w-5 h-5" />,
            title: t(workspaceConstant.allResponders),
            path: 'all-responders'
        },
        {
            icon: <UserMore className="w-5 h-5" />,
            title: t(groupConstant.groups),
            path: 'groups'
        }
    ];

    return (
        <div className="flex flex-col">
            <div className="flex items-center space-x-8 border-b border-gray-200 mb-8">
                {tabs.map((tab) => {
                    const isActive = pathname.endsWith(tab.path);
                    return (
                        <Link
                            key={tab.path}
                            href={`/${workspaceName}/dashboard/responders-groups/${tab.path}`}
                            className={cn(
                                'flex items-center px-1 py-4 text-sm font-medium border-b-2 transition-colors duration-200 mb-[-1px]',
                                isActive
                                    ? 'border-gray-900 text-gray-900'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            )}
                        >
                            <span className="mr-2">{tab.icon}</span>
                            {tab.title}
                        </Link>
                    );
                })}
            </div>
            {children}
        </div>
    );
}

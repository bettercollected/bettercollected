'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';
import { useTranslation } from 'react-i18next';

import { FormIcon } from '@Components/icons/form-icon';
import MembersIcon from '@Components/icons/members';

import BreadcrumbsRenderer from '@Components/form/breadcrumbs-renderer';
import Loader from '@app/components/ui/loader';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { useAppSelector } from '@app/store/hooks';
import { useGetRespondersGroupQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { Users } from 'lucide-react';

interface GroupPreviewLayoutClientProps {
    children: React.ReactNode;
    workspaceName: string;
    groupId: string;
}

export default function GroupPreviewLayoutClient({ children, workspaceName, groupId }: GroupPreviewLayoutClientProps) {
    const { t } = useTranslation();
    const pathname = usePathname();
    const workspace = useAppSelector(selectWorkspace);

    const { data: groupData, isLoading } = useGetRespondersGroupQuery({
        workspaceId: workspace?.id,
        groupId: groupId
    }, { skip: !workspace?.id });

    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(localesCommon.respondersAndGroups),
            url: `/${workspaceName}/dashboard/responders-groups`
        },
        {
            title: t(groupConstant.groups),
            url: `/${workspaceName}/dashboard/responders-groups/groups`
        },
        {
            title: groupData?.name,
            disabled: true
        }
    ];

    const tabs = [
        {
            icon: <Users className="w-5 h-5" />,
            title: t(groupConstant.details),
            path: 'details'
        },
        {
            icon: <MembersIcon className="w-5 h-5" />,
            title: `${t(members.default)} (${groupData?.emails?.length ?? 0})`,
            path: 'members'
        },
        {
            icon: <FormIcon className="w-5 h-5" />,
            title: `${t(localesCommon.forms)} (${groupData?.forms?.length ?? 0})`,
            path: 'forms'
        }
    ];

    if (isLoading) {
        return (
            <div className="w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    }

    return (
        <div className="flex flex-col -mt-6">
            <BreadcrumbsRenderer items={breadcrumbsItem} />
            <div className="flex items-center space-x-8 border-b border-gray-200 mb-8 mt-4">
                {tabs.map((tab) => {
                    const isActive = pathname.includes(tab.path);
                    return (
                        <Link
                            key={tab.path}
                            href={`/${workspaceName}/dashboard/responders-groups/${groupId}/${tab.path}`}
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

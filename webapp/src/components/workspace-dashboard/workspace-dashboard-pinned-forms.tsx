import React from 'react';

import { useTranslation } from 'next-i18next';

import Loader from '@app/components/ui/loader';
import WorkspaceDashboardFormsCard from '@app/components/workspace-dashboard/workspace-dashboard-form-cards';
import { localesCommon } from '@app/constants/locales/common';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { Button } from '@app/shadcn/components/ui/button';
import { useRouter } from 'next/navigation';
import environments from '@app/configs/environments';
import NewFormButton from '@app/views/atoms/NewFormButton';

interface IWorkspaceDashboardPinnedFormsProps {
    workspacePinnedForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
    title?: string;
}

export default function WorkspaceDashboardPinnedForms({ workspacePinnedForms, workspace, title, hasCustomDomain }: IWorkspaceDashboardPinnedFormsProps) {
    const { t } = useTranslation();
    const forms = workspacePinnedForms?.data?.items;

    const router = useRouter();

    if (workspacePinnedForms.isLoading) {
        return (
            <div className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );
    }

    return (
        <div className="mb-10 flex h-fit w-full flex-col gap-5">
            <div className="flex min-h-9 flex-col gap-6 md:flex-row md:items-center md:justify-between">
                <div className="sh1 flex flex-row items-center gap-6">
                    <div className={'flex flex-row gap-1'}>
                        <h1>{title || t(localesCommon.forms)}</h1>
                        <h2>{`(${forms?.length})`}</h2>
                    </div>
                </div>
                <NewFormButton />
            </div>
            <WorkspaceDashboardFormsCard workspaceForms={forms} workspace={workspace} hasCustomDomain={hasCustomDomain} />
        </div>
    );
}

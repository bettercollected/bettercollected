import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { escapeRegExp } from 'lodash';

import CreateFormButton from '@Components/Common/CreateFormButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import SearchInput from '@Components/Common/Search/SearchInput';
import BeaconComponent from '@Components/Joyride/JoyrideBeacon';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import WorkspaceDashboardFormsCard from '@app/components/workspace-dashboard/workspace-dashboard-form-cards';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { localesCommon } from '@app/constants/locales/common';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
import { useSearchWorkspaceFormsMutation } from '@app/store/workspaces/api';

interface IWorkspaceDashboardPinnedFormsProps {
    workspacePinnedForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
    title?: string;
}

export default function WorkspaceDashboardPinnedForms({ workspacePinnedForms, workspace, title, hasCustomDomain }: IWorkspaceDashboardPinnedFormsProps) {
    const { t } = useTranslation();
    const forms = workspacePinnedForms?.data?.items;
    const ref = React.useRef<HTMLDivElement>(null);

    if (workspacePinnedForms.isLoading) {
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    }

    // @ts-ignore
    return (
        <div className="w-full mb-4 flex flex-col gap-5 h-fit">
            <div className="min-h-9 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                <div className="sh1 flex flex-row gap-6 items-center">
                    <div className={'flex flex-row gap-1'}>
                        <h1>{title || t(localesCommon.forms)}</h1>
                        <h2>{`(${forms?.length})`}</h2>
                    </div>
                </div>

                <div className="flex gap-3">
                    <ImportFormsButton className={JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_IMPORT_FORM_BUTTON} />
                    <CreateFormButton />
                </div>
            </div>
            <WorkspaceDashboardFormsCard workspaceForms={forms} workspace={workspace} hasCustomDomain={hasCustomDomain} />
        </div>
    );
}

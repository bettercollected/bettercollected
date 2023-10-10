import React, { useEffect, useState } from 'react';

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
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
import { useGetWorkspaceFormsQuery, useSearchWorkspaceFormsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IWorkspaceDashboardFormsProps {
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
    title?: string;
    showButtons?: boolean;
}

export default function WorkspaceDashboardForms({ title, showButtons, hasCustomDomain }: IWorkspaceDashboardFormsProps) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceQuery = {
        workspace_id: workspace.id
    };
    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });
    const [searchWorkspaceForms] = useSearchWorkspaceFormsMutation();
    const forms = workspaceForms?.data?.items || [];
    const [allForms, setAllForms] = useState([]);

    useEffect(() => {
        if (!!workspaceForms?.data) {
            setAllForms(workspaceForms?.data?.items);
        }
    }, [workspaceForms?.data]);

    const handleSearch = async (event: any) => {
        const response: any = await searchWorkspaceForms({
            workspace_id: workspace.id,
            query: escapeRegExp(event.target.value)
        });
        setAllForms(response?.data);
    };

    if (workspaceForms.isLoading) {
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    }

    return (
        <div className="w-full mb-4 flex flex-col gap-5 h-fit">
            <div className="min-h-9 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                <div className="sh1 flex flex-row gap-6 items-center">
                    <div className={'flex flex-row gap-1'}>
                        <h1>{title || t(localesCommon.forms)}</h1>
                        <h2>{`(${forms?.length})`}</h2>
                    </div>
                    <SearchInput handleSearch={handleSearch} />
                </div>
                {showButtons && (
                    <div className="flex gap-3">
                        <ImportFormsButton className={JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_IMPORT_FORM_BUTTON} />
                        <CreateFormButton />
                    </div>
                )}
            </div>
            <WorkspaceDashboardFormsCard showPinned={true} workspaceForms={allForms} workspace={workspace} hasCustomDomain={hasCustomDomain} />
        </div>
    );
}

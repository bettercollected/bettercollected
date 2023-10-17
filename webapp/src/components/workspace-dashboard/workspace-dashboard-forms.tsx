import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { escapeRegExp } from 'lodash';

import CreateFormButton from '@Components/Common/CreateFormButton';
import StyledPagination from '@Components/Common/Pagination';
import SearchInput from '@Components/Common/Search/SearchInput';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import Loader from '@app/components/ui/loader';
import WorkspaceDashboardFormsCard from '@app/components/workspace-dashboard/workspace-dashboard-form-cards';
import globalConstants from '@app/constants/global';
import { localesCommon } from '@app/constants/locales/common';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
import { useGetWorkspaceFormsQuery, useLazySearchWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IWorkspaceDashboardFormsProps {
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
    title?: string;
    showButtons?: boolean;
    showPagination?: boolean;
}

export default function WorkspaceDashboardForms({ title, showButtons, hasCustomDomain, showPagination }: IWorkspaceDashboardFormsProps) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);

    const [showSearchedResults, setShowSearchedResults] = useState(false);

    const [workspaceQuery, setWorkspaceQuery] = useState({
        workspace_id: workspace.id,
        page: 1,
        size: globalConstants.pageSize
    });

    const [searchedForms, setSearchedForms] = useState<Array<StandardFormDto>>([]);

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, {
        pollingInterval: 30000,
        skip: !workspaceQuery.workspace_id
    });

    useEffect(() => {
        setWorkspaceQuery({ ...workspaceQuery, workspace_id: workspace.id });
    }, [workspace.id]);

    const [searchWorkspaceForms] = useLazySearchWorkspaceFormsQuery();
    const handleSearch = async (event: any) => {
        if (!event.target.value) {
            setShowSearchedResults(false);
            setSearchedForms([]);
        } else {
            const response: any = await searchWorkspaceForms({
                workspace_id: workspace.id,
                query: escapeRegExp(event.target.value)
            });
            setSearchedForms(response?.data);
            setShowSearchedResults(true);
        }
    };

    if (workspaceForms.isLoading) {
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    }

    const handlePageChange = (event: any, page: number) => {
        setWorkspaceQuery({
            ...workspaceQuery,
            page: page
        });
    };
    return (
        <div className="w-full mb-10 flex flex-col gap-5 h-fit">
            <div className="flex flex-col gap-6 mb-5 md:flex-row md:items-center md:justify-between">
                <div className="sh1 flex flex-row gap-6 items-center">
                    <div className={'flex flex-row gap-1'}>
                        <h1>{title || t(localesCommon.forms)}</h1>
                        {showPagination && <h2>{`(${showSearchedResults ? searchedForms?.length || 0 : workspaceForms?.data?.total || 0})`}</h2>}
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
            <WorkspaceDashboardFormsCard showPinned={true} showEmpty={true} workspaceForms={showSearchedResults ? searchedForms : workspaceForms?.data?.items} workspace={workspace} hasCustomDomain={hasCustomDomain} />
            {showPagination && !showSearchedResults && Array.isArray(workspaceForms?.data?.items) && workspaceForms?.data?.total > globalConstants.pageSize && (
                <div className="my-8 flex justify-center">
                    <StyledPagination shape="rounded" count={workspaceForms?.data?.pages || 0} page={workspaceQuery.page || 1} onChange={handlePageChange} />
                </div>
            )}
        </div>
    );
}

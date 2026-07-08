'use client';

import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { escapeRegExp } from 'lodash';

import StyledPagination from '@Components/common/pagination';
import SearchInput from '@Components/common/search-input';
import EmptyFormIcon from '@Components/icons/empty-form';

import Loader from '@app/components/ui/loader';
import WorkspaceDashboardFormsCard from '@app/components/workspace-dashboard/workspace-dashboard-form-cards';
import globalConstants from '@app/constants/global';
import { localesCommon } from '@app/constants/locales/common';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormsQuery, useLazySearchWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import NewFormButton from '@app/views/atoms/new-form-button';

function EmptyFormsView() {
    const { t } = useTranslation();
    return (
        <div className="flex flex-col items-center gap-[72px]">
            <div className="mt-8 flex w-full flex-col items-center gap-2">
                <EmptyFormIcon />
                <div className="h4-new text-black-800 mt-4 !leading-normal">{t('HAVE_NOT_IMPORTED_OR_CREATED')}</div>
                <div className="p2-new text-black-700 !leading-normal">{t('CREATE_OR_IMPORT')}</div>
                <div className="mt-4 flex gap-4">
                    <NewFormButton />
                    {/* <div className={'flex flex-row gap-4'}>
                        <ImportFormsButton />
                        <CreateFormButton />
                    </div> */}
                </div>
            </div>
        </div>
    );
}

interface IWorkspaceDashboardFormsProps {
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
    showButtons?: boolean;
    showPagination?: boolean;
    isWorkspace?: boolean;
}

export default function WorkspaceDashboardForms({ showButtons, hasCustomDomain, showPagination, isWorkspace = false }: IWorkspaceDashboardFormsProps) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);

    const [showSearchedResults, setShowSearchedResults] = useState(false);

    const [workspaceQuery, setWorkspaceQuery] = useState({
        workspace_id: workspace.id,
        published: isWorkspace,
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
            <div className=" flex w-full justify-center py-10">
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
        <div className="mb-10 flex h-fit w-full flex-col gap-5">
            {workspaceForms?.data?.total > 0 ? (
                <>
                    {/* The page heading lives in the top navbar (getHeader) — repeating
                        it here read as a stutter. The toolbar keeps the useful part: a
                        quiet count beside search. */}
                    <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div className="flex flex-row items-center gap-4">
                            {showPagination && (
                                <span className="text-black-600 whitespace-nowrap text-sm tabular-nums">
                                    {(showSearchedResults ? searchedForms?.length || 0 : workspaceForms?.data?.total || 0) === 1
                                        ? '1 form'
                                        : `${showSearchedResults ? searchedForms?.length || 0 : workspaceForms?.data?.total || 0} forms`}
                                </span>
                            )}
                            <SearchInput placeholder={'Search Form'} handleSearch={handleSearch} />
                        </div>
                        {showButtons && <NewFormButton />}
                    </div>
                    <WorkspaceDashboardFormsCard showPinned={true} showEmpty={showSearchedResults} workspaceForms={showSearchedResults ? searchedForms : [...workspaceForms?.data?.items]} workspace={workspace} hasCustomDomain={hasCustomDomain} />
                    {showPagination && !showSearchedResults && Array.isArray(workspaceForms?.data?.items) && workspaceForms?.data?.total > globalConstants.pageSize && (
                        <div className="my-8 flex justify-center">
                            <StyledPagination shape="rounded" count={workspaceForms?.data?.pages || 0} page={workspaceQuery.page || 1} onChange={handlePageChange} />
                        </div>
                    )}
                </>
            ) : (
                <EmptyFormsView />
            )}
        </div>
    );
}

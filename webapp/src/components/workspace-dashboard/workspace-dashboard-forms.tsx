'use client';

import { useEffect, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { escapeRegExp } from 'lodash';

import StyledPagination from '@Components/common/pagination';
import SearchInput from '@Components/common/search-input';

import GoogleFormsImportNotice from '@app/components/form-integrations/google-forms-import-notice';
import EmptyState from '@app/components/ui/empty-state';
import Loader from '@app/components/ui/loader';
import WorkspaceDashboardFormsCard from '@app/components/workspace-dashboard/workspace-dashboard-form-cards';
import globalConstants from '@app/constants/global';
import { useGoogleFormsImportMode } from '@app/lib/hooks/use-google-forms-import-mode';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormsQuery, useLazySearchWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import NewFormButton from '@app/views/atoms/new-form-button';

/** Imported from Google Forms (also once converted to a form of ours that keeps the link). */
export const isGoogleForm = (form: StandardFormDto) => form?.settings?.provider === 'google' || !!form?.importedFormId;

function EmptyFormsView() {
    const { t } = useTranslation();
    return <EmptyState title={t('STAFF.EMPTY_STATE.FORMS_TITLE')} description={t('STAFF.EMPTY_STATE.FORMS_TEXT')} action={<NewFormButton />} />;
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
    // bumped to empty the (uncontrolled) search box when the search is cleared from the empty state
    const [searchBoxKey, setSearchBoxKey] = useState(0);

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
    // Forms imported from Google Forms stay when the instance makes imports
    // read-only or turns them off; say why they no longer sync.
    const { mode: googleImportMode } = useGoogleFormsImportMode();
    const listsGoogleForms = (workspaceForms?.data?.items ?? []).some(isGoogleForm);
    const searchBoxRef = useRef<HTMLDivElement>(null);
    const focusSearchBox = useRef(false);
    const clearSearch = () => {
        setShowSearchedResults(false);
        setSearchedForms([]);
        focusSearchBox.current = true;
        setSearchBoxKey((key) => key + 1);
    };
    // the box is remounted empty; focus goes back into it, not to the page
    useEffect(() => {
        if (!focusSearchBox.current) return;
        focusSearchBox.current = false;
        searchBoxRef.current?.querySelector('input')?.focus();
    }, [searchBoxKey]);
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
                    {listsGoogleForms && (googleImportMode === 'readonly' || googleImportMode === 'off') && <GoogleFormsImportNotice mode={googleImportMode} className="max-w-[720px]" />}
                    {/* The page heading lives in the top navbar (getHeader). The toolbar
                        leads with a real-width search (the flex parent previously never
                        grew, collapsing the w-full input to ~200px) and carries the count
                        as a quiet, search-aware suffix aligned to the control. */}
                    <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div className="flex w-full min-w-0 flex-1 items-center gap-3">
                            <div ref={searchBoxRef} className="w-full max-w-[420px]">
                                <SearchInput key={searchBoxKey} placeholder={t(formConstant.toolbar.searchPlaceholder)} handleSearch={handleSearch} />
                            </div>
                            {showPagination && (
                                <span className="text-black-600 shrink-0 whitespace-nowrap text-sm tabular-nums">
                                    {t(formConstant.toolbar.count, { count: showSearchedResults ? searchedForms?.length || 0 : workspaceForms?.data?.total || 0 })}
                                </span>
                            )}
                        </div>
                        {showButtons && <NewFormButton />}
                    </div>
                    <WorkspaceDashboardFormsCard showPinned={true} showEmpty={showSearchedResults} onClearSearch={clearSearch} workspaceForms={showSearchedResults ? searchedForms : [...workspaceForms?.data?.items]} workspace={workspace} hasCustomDomain={hasCustomDomain} />
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

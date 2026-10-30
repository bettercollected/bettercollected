import { useCallback, useEffect, useMemo, useRef, useState } from 'react';


import SearchInput from '@Components/common/search-input';
import TabularResponses from '@Components/form/tabular-responses';

import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery, useLazyExportFormSubmissionsQuery } from '@app/store/workspaces/api';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';
import EmptyResponseIcon from '@Components/icons/expty-response-icon';
import { DownloadIcon } from 'lucide-react';
import ResponsesTable from './responses-table';
//@ts-ignore
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { buildResponsesExport, exportFileName, tableToCsv } from '@app/utils/response-export';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

function downloadCsv(csv: string, fileName: string) {
    // BOM so spreadsheet apps read UTF-8 names correctly.
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function FormResponsesTable({ props }: any) {
    const form = useAppSelector(selectForm);

    const { workspace, requestForDeletion, isSubmission = false } = props;
    const [page, setPage] = useState(1);
    // The search text lives here, next to the one query it drives; the table
    // below only displays what this query returns.
    const [searchText, setSearchText] = useState('');

    const query = useMemo<IGetFormSubmissionsQuery>(
        () => ({
            formId: form.formId,
            workspaceId: workspace?.id,
            requestedForDeletionOly: !!requestForDeletion,
            page,
            size: globalConstants.pageSize,
            ...(searchText ? { dataOwnerIdentifier: searchText } : {})
        }),
        [form.formId, workspace?.id, requestForDeletion, page, searchText]
    );

    const { data, isLoading, isFetching, isError, refetch } = useGetFormsSubmissionsQuery(query, { skip: !workspace?.id });
    const { can } = useWorkspacePermissions();
    const canExport = can(WorkspacePermission.RESPONSE_EXPORT);
    const [trigger, { isLoading: csvLoading }] = useLazyExportFormSubmissionsQuery();

    const handleSearch = useCallback((event: any) => {
        // a new search starts on the first page
        setSearchText(String(event?.target?.value ?? '').trim());
        setPage(1);
    }, []);

    const handleClickExportCSV = () => {
        trigger({ formId: form.formId, workspaceId: workspace?.id }).then((result) => {
            // never a header-only file for a refused export
            if (result.isError) return;
            // One row per submission; repeating groups become columns per item,
            // or (large groups) a CSV of their own with one row per item.
            const { main, groupTables } = buildResponsesExport(form, (result.data ?? []) as Array<StandardFormResponseDto>);
            // Every file goes through tableToCsv, which neutralises formula-like cells.
            downloadCsv(tableToCsv(main), exportFileName(form.title));
            groupTables.forEach((table) => downloadCsv(tableToCsv(table), exportFileName(form.title, table.name)));
        });
    };

    const hasItems = !!data && Array.isArray(data.items) && data.items.length > 0;
    // A later page that came back empty (its last rows were deleted or their
    // requests closed) is not "no responses": step back to the last page that
    // still has rows (a failed request stays an error).
    const lastPage = Math.max(1, data?.pages || 1);
    const pageEmptied = !!data && !hasItems && page > 1 && !isError;
    useEffect(() => {
        if (pageEmptied && !isFetching) setPage((current) => Math.max(1, Math.min(current - 1, lastPage)));
    }, [pageEmptied, isFetching, lastPage]);

    // Retry replaces the error (and its button) with the loader; focus moves to
    // the results region so it does not fall to <body>.
    const resultsRef = useRef<HTMLDivElement>(null);
    const handleRetry = useCallback(() => {
        resultsRef.current?.focus();
        refetch();
    }, [refetch]);

    let results;
    // No workspace yet: the query is skipped, which is not "no responses".
    // Asking with nothing to show yet (a retry after an error, a new or
    // cleared search after a no-match one, a page that emptied) is loading
    // too: never an empty or no-match state before the server has answered.
    if (isLoading || !workspace?.id || (isFetching && !hasItems) || pageEmptied) {
        results = (
            <div role="status" aria-label="Loading responses" className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );
    } else if (isError) {
        // A refused or failed request is not an empty form: say so, and let
        // the person try again.
        results = <ResponsesErrorComponent onRetry={handleRetry} />;
    } else if (hasItems) {
        results = (
            <div aria-busy={isFetching} className={isFetching ? 'opacity-50 transition-opacity' : 'transition-opacity'}>
                {requestForDeletion ? (
                    <ResponsesTable formId={form.formId} requestForDeletion={requestForDeletion} page={page} setPage={setPage} submissions={data!} />
                ) : (
                    <TabularResponses form={form} data={data} page={page} onPageChange={setPage} />
                )}
            </div>
        );
    } else if (searchText) {
        results = <NoMatchComponent searchText={searchText} requestForDeletion={requestForDeletion} />;
    } else {
        results = <EmptyTabularResponseComponent requestForDeletion={requestForDeletion} />;
    }

    return (
        <div>
            <div className={`mb-6 flex flex-col gap-2 lg:flex-row lg:justify-between`}>
                <div className="flex w-full flex-row justify-between">
                    {(isSubmission && form.responses) || (!isSubmission && form.deletionRequests) ? (
                        <div className="flex w-full flex-row items-center gap-4 ">
                            <SearchInput
                                handleSearch={handleSearch}
                                placeholder={'Search by responder email'}
                                ariaLabel={requestForDeletion ? 'Search deletion requests by responder email' : 'Search responses by responder email'}
                                className="md:w-[282px]"
                            />
                        </div>
                    ) : (
                        <></>
                    )}
                    {isSubmission && canExport && (
                        <Button data-umami-event="Export CSV Button" isLoading={csvLoading} variant="v2Button" icon={<DownloadIcon className="h-4 w-4" />} onClick={handleClickExportCSV} className={''}>
                            Export CSV
                        </Button>
                    )}
                </div>
            </div>
            <div ref={resultsRef} tabIndex={-1} role="region" aria-label={requestForDeletion ? 'Deletion requests' : 'Responses'} className="focus:outline-hidden">
                {results}
            </div>
        </div>
    );
}

const ResponsesErrorComponent = ({ onRetry }: { onRetry: () => void }) => (
    <div role="alert" className={'flex flex-col items-center gap-2 py-10'}>
        <EmptyResponseIcon />
        <span className={'p3-new text-black'}>Could not load responses</span>
        <span className={'p4-new text-black-600 max-w-[420px] text-center'}>Something went wrong, or you may not have access. Your responses are not affected.</span>
        <Button type="button" variant="v2Button" onClick={() => onRetry()} className="mt-2">
            Retry
        </Button>
    </div>
);

const NoMatchComponent = ({ searchText, requestForDeletion }: { searchText: string; requestForDeletion?: boolean }) => (
    <div role="status" className={'flex flex-col items-center gap-2 py-10'}>
        <EmptyResponseIcon />
        <span className={'p3-new text-black'}>{requestForDeletion ? 'No deletion requests match' : 'No responses match'}</span>
        <span className={'p4-new text-black-600 max-w-[420px] break-words text-center'}>
            Nothing matches &ldquo;{searchText}&rdquo;. The search looks at the responder&apos;s email address; anonymous responses cannot be found by it.
        </span>
    </div>
);

const EmptyTabularResponseComponent = ({ requestForDeletion }: { requestForDeletion?: boolean }) => {
    // Deletion requests are a GDPR feature — the empty state should teach that,
    // not borrow the responses copy (which can be factually wrong here).
    if (requestForDeletion) {
        return (
            <div className={'flex flex-col items-center gap-2 py-10'}>
                <EmptyResponseIcon />
                <span className={'p3-new text-black'}>No deletion requests</span>
                <span className={'p4-new text-black-600 max-w-[420px] text-center'}>When a responder asks for their response to be deleted, it shows up here for you to act on.</span>
            </div>
        );
    }
    return (
        <div className={'flex flex-col items-center gap-2 py-10'}>
            <EmptyResponseIcon />
            <span className={'p3-new text-black'}>No responses yet</span>
            <span className={'p4-new text-black-600'}>Responses appear here as soon as someone fills out your form.</span>
        </div>
    );
};

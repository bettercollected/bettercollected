import { useCallback, useEffect, useMemo, useRef, useState } from 'react';


import SearchInput from '@Components/common/search-input';
import TabularResponses from '@Components/form/tabular-responses';

import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';
import EmptyResponseIcon from '@Components/icons/expty-response-icon';
import ResponseExportControl from './response-export-control';
import ResponsesTable from './responses-table';
//@ts-ignore
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { rememberResponseListPage, rememberResponseListView, rememberedListView } from '@app/utils/response-list-memory';

export default function FormResponsesTable({ props }: any) {
    const form = useAppSelector(selectForm);

    const { workspace, requestForDeletion, isSubmission = false } = props;
    // Back from a response's page (its link, or the browser's Back), the
    // responses list opens on the page and search it was left on. Both are
    // kept in memory only (utils/response-list-memory.ts), never in the URL:
    // the search is often a responder's email.
    const [restored] = useState(() => (requestForDeletion ? null : rememberedListView(workspace?.id, form.formId)));
    const [page, setPage] = useState(restored?.page ?? 1);
    // The search text lives here, next to the one query it drives; the table
    // below only displays what this query returns.
    const [searchText, setSearchText] = useState(restored?.searchText ?? '');

    useEffect(() => {
        if (!requestForDeletion) rememberResponseListView({ workspaceId: workspace?.id ?? '', formId: form.formId, searchText }, page);
    }, [requestForDeletion, workspace?.id, form.formId, searchText, page]);

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

    const { data, currentData, isLoading, isFetching, isError, refetch } = useGetFormsSubmissionsQuery(query, { skip: !workspace?.id });
    const { can } = useWorkspacePermissions();
    const canExport = can(WorkspacePermission.RESPONSE_EXPORT);

    const handleSearch = useCallback((event: any) => {
        // a new search starts on the first page
        setSearchText(String(event?.target?.value ?? '').trim());
        setPage(1);
    }, []);

    const hasItems = !!data && Array.isArray(data.items) && data.items.length > 0;
    // A page past the end of the list (its last rows were deleted or their
    // requests closed, here or by someone else, for example while a
    // response's page was open): go to the last page that still has rows,
    // keeping the pagination; "No responses yet" is only for a form that has
    // none. Each step goes at least one page back, so this ends. Only the
    // answer for this very page counts (`currentData`, never the previous
    // page's rows while this one loads), and a failed request stays an error.
    // Set while rendering, as React advises for state that follows from
    // other state.
    const pastTheEnd = !!currentData && Array.isArray(currentData.items) && currentData.items.length === 0 && page > 1 && !isError;
    if (pastTheEnd) {
        const last = Math.max(1, Math.ceil((currentData.total ?? 0) / (currentData.size || globalConstants.pageSize)));
        setPage(Math.max(1, Math.min(page - 1, last)));
    }

    // The order on screen (ids only), for "previous"/"next" on a response's
    // page. Only from `currentData`: `data` still holds the previous page's
    // rows while the next one loads, and a failed load would leave those ids
    // under the new page number.
    useEffect(() => {
        if (requestForDeletion || pastTheEnd || !Array.isArray(currentData?.items)) return;
        rememberResponseListPage(
            { workspaceId: workspace?.id ?? '', formId: form.formId, searchText },
            { page, size: currentData.size ?? currentData.items.length, total: currentData.total ?? currentData.items.length, ids: currentData.items.map((item: StandardFormResponseDto) => item.responseId) }
        );
    }, [requestForDeletion, pastTheEnd, currentData, page, form.formId, workspace?.id, searchText]);

    // Retry replaces the error (and its button) with the loader until the
    // server answers, even when older rows are still at hand; focus moves to
    // the results region so it does not fall to <body>.
    const resultsRef = useRef<HTMLDivElement>(null);
    const [retrying, setRetrying] = useState(false);
    const retryStarted = useRef(false);
    useEffect(() => {
        if (!retrying) return;
        if (isFetching) retryStarted.current = true;
        // the retry answered (an error again, or rows), or an answer is in anyway
        else if (retryStarted.current || !isError) {
            retryStarted.current = false;
            setRetrying(false);
        }
    }, [retrying, isFetching, isError]);
    const handleRetry = useCallback(() => {
        retryStarted.current = false;
        setRetrying(true);
        resultsRef.current?.focus();
        try {
            refetch();
        } catch {
            setRetrying(false);
        }
    }, [refetch]);

    let results;
    // No workspace yet: the query is skipped, which is not "no responses".
    // Asking with no answer for this list yet (a retry, a new or cleared
    // search after a no-match one, a page stepped back to) is loading too:
    // never an empty or no-match state before the server has answered. A
    // refetch of the same list (tab focus, an invalidated cache) keeps its
    // answer in `currentData`, so its state stays on screen.
    const waiting = isFetching && currentData === undefined && !hasItems;
    if (isLoading || !workspace?.id || pastTheEnd || retrying || waiting) {
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
                                defaultValue={searchText}
                                placeholder={'Search by responder email'}
                                ariaLabel={requestForDeletion ? 'Search deletion requests by responder email' : 'Search responses by responder email'}
                                className="md:w-[282px]"
                            />
                        </div>
                    ) : (
                        <></>
                    )}
                    {isSubmission && canExport && <ResponseExportControl workspaceId={workspace?.id} formId={form.formId} formTitle={form.title} search={searchText} />}
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

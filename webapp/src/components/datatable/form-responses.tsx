import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { useTranslation } from 'react-i18next';

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
import ResponseExportControl, { ExportFilters } from './response-export-control';
import ResponsesTable from './responses-table';
//@ts-ignore
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { rememberResponseListPage, rememberResponseListView, rememberedListView } from '@app/utils/response-list-memory';
import { responsesListLocale as text } from '@app/constants/locales/responses-list';
import { DEFAULT_STATE, PageSize, ResponseListState, activeFilterCount, hasListParams, parseResponseListState, responseListApiParams, responseListSearchParams, responseListView } from '@app/utils/response-list-state';
import ResponseFilters from './response-filters';
import ResponsePager from './response-pager';

export default function FormResponsesTable({ props }: any) {
    const form = useAppSelector(selectForm);

    const { workspace, requestForDeletion, isSubmission = false } = props;
    const { t, i18n } = useTranslation();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    // Back from a response's page (its link), the responses list opens on the
    // filters, page and search it was left on: the list's own URL parameters
    // and the search are kept in memory only (utils/response-list-memory.ts);
    // the search never goes into the URL (it is often a responder's email).
    const [restored] = useState(() => (requestForDeletion ? null : rememberedListView(workspace?.id, form.formId)));
    // The responses list lives in the URL (page, size, sort, filters), so it
    // can be shared and Back/Forward walk through it; the deletion requests
    // keep a page of their own in state, as before.
    const urlState = useMemo(() => parseResponseListState(searchParams ?? new URLSearchParams()), [searchParams]);
    const filtersActive = activeFilterCount(urlState) > 0;
    const [deletionPage, setDeletionPage] = useState(1);
    const state: ResponseListState = requestForDeletion ? { ...DEFAULT_STATE, page: deletionPage } : urlState;
    const page = state.page;
    // The search text lives here, next to the one query it drives; the table
    // below only displays what this query returns.
    const [searchText, setSearchText] = useState(restored?.searchText ?? '');
    // No parameters in the URL but a remembered list: open it there (once).
    // Until the router has the remembered address, nothing is asked for. Once
    // only: stepping back to a list with no parameters (page 1, the defaults)
    // later is a list of its own, not a reason to restore again.
    const needsRestore = !requestForDeletion && !!restored?.query && !hasListParams(searchParams ?? new URLSearchParams());
    const [restoreStarted, setRestoreStarted] = useState(false);
    const restoring = needsRestore && !restoreStarted;
    useEffect(() => {
        if (needsRestore && restored?.query) router.replace(`${pathname}?${restored.query}`, { scroll: false });
        setRestoreStarted(true);
        // once, on opening
    }, []);

    /** Move to another state of the list: a new entry in the history. */
    const navigate = useCallback(
        (next: ResponseListState, replace = false) => {
            const query = responseListSearchParams(next).toString();
            const url = query ? `${pathname}?${query}` : pathname;
            if (replace) router.replace(url, { scroll: false });
            else router.push(url, { scroll: false });
        },
        [pathname, router]
    );
    const setPage = useCallback(
        (next: number) => {
            if (requestForDeletion) setDeletionPage(next);
            else navigate({ ...urlState, page: next, cursor: undefined }, true);
        },
        [requestForDeletion, navigate, urlState]
    );
    // a filter, the sort or the size starts again on the first page, without a cursor
    const change = useCallback((changes: Partial<ResponseListState>) => navigate({ ...urlState, ...changes, page: 1, cursor: undefined }), [navigate, urlState]);
    const clearFilters = useCallback(() => navigate({ ...urlState, from: undefined, to: undefined, status: undefined, who: undefined, version: undefined, page: 1, cursor: undefined }), [navigate, urlState]);

    const view = responseListView(state);
    const listQuery = responseListSearchParams(state).toString();
    useEffect(() => {
        if (!requestForDeletion && !restoring) rememberResponseListView({ workspaceId: workspace?.id ?? '', formId: form.formId, searchText, view }, page, listQuery);
    }, [requestForDeletion, restoring, workspace?.id, form.formId, searchText, view, page, listQuery]);

    const query = useMemo<IGetFormSubmissionsQuery>(
        () =>
            requestForDeletion
                ? {
                      formId: form.formId,
                      workspaceId: workspace?.id,
                      requestedForDeletionOly: true,
                      page,
                      size: globalConstants.pageSize,
                      ...(searchText ? { dataOwnerIdentifier: searchText } : {})
                  }
                : {
                      formId: form.formId,
                      workspaceId: workspace?.id,
                      requestedForDeletionOly: false,
                      ...responseListApiParams(state),
                      ...(searchText ? { dataOwnerIdentifier: searchText } : {})
                  },
        // `state` is read through its serialised parts
        [form.formId, workspace?.id, requestForDeletion, listQuery, page, searchText]
    );

    // what the Export button holds: the list's filters, by the API's names (never the page or the sort)
    const exportFilters = useMemo(() => {
        const api = responseListApiParams(state);
        const filters: ExportFilters = {};
        if (api.submittedFrom) filters.submittedFrom = api.submittedFrom;
        if (api.submittedTo) filters.submittedTo = api.submittedTo;
        if (api.status) filters.status = [api.status];
        if (api.respondent) filters.respondent = api.respondent;
        if (api.formVersion !== undefined) filters.formVersion = [api.formVersion];
        return filters;
        // `state` is read through its serialised parts
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [listQuery]);

    const { data, currentData, isLoading, isFetching, isError, error, refetch } = useGetFormsSubmissionsQuery(query, { skip: !workspace?.id || restoring });
    const errorCode = (error as { data?: { code?: string } } | undefined)?.data?.code;
    const { can } = useWorkspacePermissions();
    const canExport = can(WorkspacePermission.RESPONSE_EXPORT);

    const handleSearch = useCallback(
        (event: any) => {
            // a new search starts on the first page (a cursor is only good for the search it was issued for)
            setSearchText(String(event?.target?.value ?? '').trim());
            setPage(1);
        },
        [setPage]
    );

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
    const lastPage = Math.max(1, Math.ceil((currentData?.total ?? 0) / (currentData?.size || globalConstants.pageSize)));
    if (pastTheEnd && requestForDeletion) setPage(Math.max(1, Math.min(page - 1, lastPage)));
    // The responses list keeps its page in the URL: leaving it is a navigation, so an effect.
    useEffect(() => {
        if (pastTheEnd && !requestForDeletion) navigate({ ...urlState, page: Math.max(1, Math.min(page - 1, lastPage)), cursor: undefined }, true);
    }, [pastTheEnd, requestForDeletion, page, lastPage]);
    // A cursor that is not for this list (a link made with another search, or
    // an old one): ask again without it, which costs nothing but the seek.
    const badCursor = !requestForDeletion && isError && errorCode === 'invalid_cursor' && !!urlState.cursor;
    useEffect(() => {
        if (badCursor) navigate({ ...urlState, cursor: undefined }, true);
    }, [badCursor]);
    const tooDeep = !requestForDeletion && isError && errorCode === 'page_too_deep';

    // The order on screen (ids only), for "previous"/"next" on a response's
    // page. Only from `currentData`: `data` still holds the previous page's
    // rows while the next one loads, and a failed load would leave those ids
    // under the new page number.
    useEffect(() => {
        if (requestForDeletion || pastTheEnd || !Array.isArray(currentData?.items)) return;
        rememberResponseListPage(
            { workspaceId: workspace?.id ?? '', formId: form.formId, searchText, view },
            {
                page,
                size: currentData.size ?? currentData.items.length,
                // a capped total is not a position to quote ("n of 10,000")
                total: currentData.totalExact === false ? undefined : currentData.total ?? currentData.items.length,
                ids: currentData.items.map((item: StandardFormResponseDto) => item.responseId)
            }
        );
    }, [requestForDeletion, pastTheEnd, currentData, page, form.formId, workspace?.id, searchText, view]);

    // Retry replaces the error (and its button) with the loader until the
    // server answers, even when older rows are still at hand; focus moves to
    // the results region so it does not fall to <body>.
    const resultsRef = useRef<HTMLDivElement>(null);
    // After a page link is followed, focus moves to the results once the new
    // page is in: a keyboard or screen reader user starts at the table, not
    // wherever the old link was; the count says which rows these are.
    const focusAfterPaging = useRef(false);
    const markPaging = useCallback(() => {
        focusAfterPaging.current = true;
    }, []);
    useEffect(() => {
        if (isError) focusAfterPaging.current = false;
        if (!focusAfterPaging.current || !currentData || currentData.page !== page) return;
        focusAfterPaging.current = false;
        resultsRef.current?.focus({ preventScroll: true });
        resultsRef.current?.scrollIntoView?.({ block: 'start' });
    }, [currentData, page, isError]);
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
            <div role="status" aria-label={t('RESPONSES_STAFF.LOADING')} className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );
    } else if (tooDeep) {
        results = <TooDeepComponent onFirst={() => navigate({ ...urlState, page: 1, cursor: undefined })} />;
    } else if (isError) {
        // A refused or failed request is not an empty form: say so, and let
        // the person try again.
        results = <ResponsesErrorComponent onRetry={handleRetry} />;
    } else if (hasItems) {
        results = (
            <div aria-busy={isFetching} className={isFetching ? 'opacity-50 transition-opacity' : 'transition-opacity'}>
                {requestForDeletion ? <ResponsesTable formId={form.formId} requestForDeletion={requestForDeletion} page={page} setPage={setPage} submissions={data!} /> : <TabularResponses form={form} data={data} />}
            </div>
        );
    } else if (!requestForDeletion && filtersActive) {
        results = <NoFilterMatchComponent onClear={clearFilters} />;
    } else if (searchText) {
        results = <NoMatchComponent searchText={searchText} requestForDeletion={requestForDeletion} />;
    } else {
        results = <EmptyTabularResponseComponent requestForDeletion={requestForDeletion} />;
    }

    // The pager, the count and where focus goes after paging (responses list only).
    const shown = !requestForDeletion && !isError && hasItems ? data : undefined;
    const shownPage = shown?.page ?? page;
    const shownSize = shown?.size ?? state.size;
    const totalExact = shown?.totalExact !== false;
    const hasNext = shown?.hasNext ?? shownPage * shownSize < (shown?.total ?? 0);
    const formatNumber = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
    const countText = shown
        ? t(text.showing, {
              from: formatNumber((shownPage - 1) * shownSize + 1),
              to: formatNumber((shownPage - 1) * shownSize + shown.items.length),
              total: `${formatNumber(shown.total)}${totalExact ? '' : '+'}`
          })
        : '';
    const hrefFor = (target: number, near: boolean) => {
        // the shown page's cursor reaches the pages near it; first and last need none
        const cursor = near && shown?.cursor && shown.page === shownPage ? shown.cursor : undefined;
        const query = responseListSearchParams({ ...urlState, page: target, cursor }).toString();
        return query ? `${pathname}?${query}` : pathname;
    };
    const pagerProps = shown && {
        page: shownPage,
        size: shownSize,
        total: shown.total,
        totalExact,
        hasNext,
        hrefFor,
        onNavigate: markPaging
    };
    const showFilters = !requestForDeletion && isSubmission && (!!form.responses || filtersActive);

    const hasSearch = (isSubmission && form.responses) || (!isSubmission && form.deletionRequests);
    const searchNode = hasSearch ? (
        <div className="w-full sm:w-[320px]">
            <SearchInput
                handleSearch={handleSearch}
                defaultValue={searchText}
                placeholder={t('RESPONSES_STAFF.SEARCH_PLACEHOLDER')}
                ariaLabel={t(requestForDeletion ? 'RESPONSES_STAFF.SEARCH_LABEL_DELETION' : 'RESPONSES_STAFF.SEARCH_LABEL')}
                maxLength={320}
            />
        </div>
    ) : null;
    const exportNode = isSubmission && canExport ? <ResponseExportControl workspaceId={workspace?.id} formId={form.formId} formTitle={form.title} search={searchText} filters={exportFilters} /> : null;

    return (
        <div>
            {showFilters ? (
                <ResponseFilters state={urlState} currentVersion={form.version} onChange={change} onClear={clearFilters} search={searchNode} trailing={exportNode} />
            ) : (
                <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    {searchNode ?? <span />}
                    {exportNode}
                </div>
            )}
            {!requestForDeletion && (
                <div className="mb-3 flex min-h-9 flex-wrap items-center justify-between gap-2">
                    {/* a polite live region: the new count is announced when a page, filter or sort has loaded */}
                    <p role="status" aria-live="polite" aria-atomic="true" className="p4-new text-black-600">
                        {countText}
                    </p>
                    {pagerProps && <ResponsePager label={t(text.pagerTop)} {...pagerProps} />}
                </div>
            )}
            <div ref={resultsRef} tabIndex={-1} role="region" aria-label={t(requestForDeletion ? 'RESPONSES_STAFF.REGION_DELETION' : 'RESPONSES_STAFF.REGION')} className="focus:outline-hidden">
                {results}
            </div>
            {pagerProps && (
                <div className="mt-6">
                    <ResponsePager label={t(text.pagerBottom)} {...pagerProps} onSizeChange={(size: PageSize) => change({ size })} />
                </div>
            )}
        </div>
    );
}

const ResponsesErrorComponent = ({ onRetry }: { onRetry: () => void }) => {
    const { t } = useTranslation();
    return (
        <div role="alert" className={'flex flex-col items-center gap-2 py-10'}>
            <EmptyResponseIcon />
            <span className={'p3-new text-black'}>{t('RESPONSES_STAFF.ERROR_TITLE')}</span>
            <span className={'p4-new text-black-600 max-w-[420px] text-center'}>{t('RESPONSES_STAFF.ERROR_BODY')}</span>
            <Button type="button" variant="v2Button" onClick={() => onRetry()} className="mt-2">
                {t('RESPONSES_STAFF.RETRY')}
            </Button>
        </div>
    );
};

const NoFilterMatchComponent = ({ onClear }: { onClear: () => void }) => {
    const { t } = useTranslation();
    return (
        <div role="status" className={'flex flex-col items-center gap-2 py-10'}>
            <EmptyResponseIcon />
            <span className={'p3-new text-black'}>{t(text.noneMatchTitle)}</span>
            <span className={'p4-new text-black-600 max-w-[420px] text-center'}>{t(text.noneMatchBody)}</span>
            <Button type="button" variant="v2Button" onClick={onClear} className="mt-2">
                {t(text.clear)}
            </Button>
        </div>
    );
};

const TooDeepComponent = ({ onFirst }: { onFirst: () => void }) => {
    const { t } = useTranslation();
    return (
        <div role="alert" className={'flex flex-col items-center gap-2 py-10'}>
            <EmptyResponseIcon />
            <span className={'p3-new text-black'}>{t(text.tooDeepTitle)}</span>
            <span className={'p4-new text-black-600 max-w-[420px] text-center'}>{t(text.tooDeepBody)}</span>
            <Button type="button" variant="v2Button" onClick={onFirst} className="mt-2">
                {t(text.goFirst)}
            </Button>
        </div>
    );
};

const NoMatchComponent = ({ searchText, requestForDeletion }: { searchText: string; requestForDeletion?: boolean }) => {
    const { t } = useTranslation();
    return (
        <div role="status" className={'flex flex-col items-center gap-2 py-10'}>
            <EmptyResponseIcon />
            <span className={'p3-new text-black'}>{t(requestForDeletion ? 'RESPONSES_STAFF.NO_MATCH_TITLE_DELETION' : 'RESPONSES_STAFF.NO_MATCH_TITLE')}</span>
            <span className={'p4-new text-black-600 max-w-[420px] break-words text-center'}>{t('RESPONSES_STAFF.NO_MATCH_BODY', { search: searchText })}</span>
        </div>
    );
};

const EmptyTabularResponseComponent = ({ requestForDeletion }: { requestForDeletion?: boolean }) => {
    const { t } = useTranslation();
    // Deletion requests are a GDPR feature — the empty state should teach that,
    // not borrow the responses copy (which can be factually wrong here).
    if (requestForDeletion) {
        return (
            <div className={'flex flex-col items-center gap-2 py-10'}>
                <EmptyResponseIcon />
                <span className={'p3-new text-black'}>{t('RESPONSES_STAFF.EMPTY_DELETION_TITLE')}</span>
                <span className={'p4-new text-black-600 max-w-[420px] text-center'}>{t('RESPONSES_STAFF.EMPTY_DELETION_BODY')}</span>
            </div>
        );
    }
    return (
        <div className={'flex flex-col items-center gap-2 py-10'}>
            <EmptyResponseIcon />
            <span className={'p3-new text-black'}>{t('RESPONSES_STAFF.EMPTY_TITLE')}</span>
            <span className={'p4-new text-black-600 max-w-[420px] text-center'}>{t('RESPONSES_STAFF.EMPTY_BODY')}</span>
        </div>
    );
};

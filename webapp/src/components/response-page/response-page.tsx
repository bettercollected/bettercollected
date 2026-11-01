'use client';

import { forwardRef, useEffect, useMemo, useRef, useState } from 'react';

import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import AnonymousBadge from '@Components/datatable/anonymous-badge';
import InternalFieldsPanel from '@Components/form/internal-fields-panel';
import RespondentFeedbackPanel from '@Components/form/respondent-feedback-panel';
import DeleteIcon from '@Components/icons/delete';
import { ArrowLeft, ChevronLeft, ChevronRight, ListOrdered, Printer } from 'lucide-react';

import { UnreadableNotice } from '@app/components/form/individual-form-response';
import { useModal } from '@app/components/modal-views/context';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateTimeWithZone } from '@app/utils/date-utils';
import { getInternalFields } from '@app/utils/internal-fields';
import { shortReceiptNumber } from '@app/utils/receipt-number';
import { rememberedNeighbours } from '@app/utils/response-list-memory';
import { responseOriginListUrl, responsePageSections, responsePageUrl } from '@app/utils/response-page';
import { formVersionUrl } from '@app/utils/response-urls';
import { ResponseOrigin } from '@app/utils/response-urls';

import ReadOnlyForm, { CONTENTS_HEADING_ID, CONTENTS_ID, followInPageLink } from './read-only-form';
import ResponsePdfButton from './response-pdf-button';

/** The message keys for a failed load. A 403 and a 404 are answers, not faults: no Retry for them. */
function failureOf(error: any): { kind: 'forbidden' | 'missing' | 'error'; title: string; detail: string } {
    const status = error?.status;
    if (status === 403) return { kind: 'forbidden', title: 'RESPONSE_PAGE.FORBIDDEN_TITLE', detail: 'RESPONSE_PAGE.FORBIDDEN_BODY' };
    if (status === 404) return { kind: 'missing', title: 'RESPONSE_PAGE.MISSING_TITLE', detail: 'RESPONSE_PAGE.MISSING_BODY' };
    return { kind: 'error', title: 'RESPONSE_PAGE.ERROR_TITLE', detail: 'RESPONSE_PAGE.ERROR_BODY' };
}

const pageGutter = 'px-4 md:px-10 lg:px-28';

// Set by a previous/next link to the response it goes to: that response's
// page moves focus to its details once loaded, so a screen reader hears that
// the response changed (the tab title stays the same). Not on a first open
// (focus starts at the top), not for a click that opens a new tab, and
// forgotten when that response fails to load or another one opens instead.
let focusDetailsOf: string | null = null;

/**
 * One response on its own page, for staff: a toolbar (back to the list,
 * previous and next, PDF, print, delete), who answered and when, then the response
 * drawn like the form (ReadOnlyForm), then the staff-only parts (the team's
 * updates to the respondent and the internal fields).
 *
 * Access stays on the server: the submission endpoint checks response.read
 * and this page shows its answer (403, 404) or an error with Retry; a failed
 * load is never drawn as "no answers". The URL holds the response id only.
 */
export default function ResponsePage({ formId, responseId, origin }: { formId: string; responseId: string; origin?: ResponseOrigin }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const { can, formRevisionsUiEnabled } = useWorkspacePermissions();
    const { openModal } = useModal();
    const workspaceId = workspace?.id ?? '';
    // While the response is being deleted the page stops asking for it: the
    // delete invalidates it, and a refetch would flash "not found" before the
    // page is left. What is on screen stays (frozen) until then.
    const [frozen, setFrozen] = useState<any>(null);
    const deleting = frozen !== null;
    // currentData: never the previous response while the next one loads
    const { currentData: fetched, error, isError: fetchFailed, refetch } = useGetWorkspaceSubmissionQuery({ workspace_id: workspaceId, submission_id: responseId }, { skip: !workspaceId || deleting, refetchOnMountOrArgChange: true });
    const currentData = deleting ? frozen : fetched;
    const isError = !deleting && fetchFailed;

    // the responses list the staff member came from (ids only, in memory: utils/response-list-memory.ts);
    // none when the page was opened from a deletion-requests list
    const neighbours = useMemo(() => (origin ? {} : rememberedNeighbours(workspaceId, formId, responseId)), [origin, workspaceId, formId, responseId]);

    const response = currentData?.response;
    const form = currentData?.form;
    // a response of another form is not found here
    const wrongForm = !!response && !!form?.formId && form.formId !== formId;

    // (The tab title, "Response · <form title>", is the route's metadata: page.tsx. Not set here as well.)
    const formTitle = form?.title?.trim() || t('RESPONSE_PAGE.UNTITLED_FORM');

    // back to the list the page was opened from (a fixed path for each origin, never an address from the URL)
    const listUrl = responseOriginListUrl(workspace?.workspaceName ?? '', formId, origin);
    const listName = t(origin ? 'RESPONSE_PAGE.LIST_DELETION' : 'RESPONSE_PAGE.LIST_RESPONSES');
    // As in the deletion-requests table: completing a pending deletion request is also privacy.manage.
    const canDelete = can(WorkspacePermission.RESPONSE_DELETE) || (response?.deletionStatus === 'pending' && can(WorkspacePermission.PRIVACY_MANAGE));
    const failure = isError ? failureOf(error) : wrongForm ? failureOf({ status: 404 }) : null;
    const loaded = !!response && !!form && !wrongForm;

    const staffFields = loaded ? (currentData?.internalFields ?? getInternalFields(form)) : [];
    // a form of several pages gets a contents list (ReadOnlyForm); the toolbar, which stays in view, links back to it
    const hasContents = loaded && responsePageSections(form, response.answers ?? {}).length > 1;

    const detailsRef = useRef<HTMLElement>(null);
    const failed = !!failure;
    useEffect(() => {
        if (focusDetailsOf === null) return;
        // meant for another response (its navigation never happened), or this one failed to load
        if (focusDetailsOf !== responseId || failed) {
            focusDetailsOf = null;
            return;
        }
        if (!loaded) return;
        focusDetailsOf = null;
        detailsRef.current?.focus();
    }, [loaded, failed, responseId]);

    return (
        <div className="min-h-dvh bg-white text-black-900 print:min-h-0">
            {/* opaque: the page scrolls under it */}
            <header className={`sticky top-0 z-30 border-b border-black-300 bg-white print:hidden ${pageGutter}`}>
                <nav aria-label={t('RESPONSE_PAGE.ACTIONS')} className="flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2">
                    <Link href={listUrl} className="flex min-w-0 items-center gap-2 rounded text-sm font-medium text-black-700 hover:text-black-900 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500">
                        <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden="true" />
                        <span>{listName}</span>
                        {form && !wrongForm && <span className="max-w-[40vw] truncate font-normal text-black-600 sm:max-w-[320px]">· {formTitle}</span>}
                    </Link>
                    {/* At phone width the labels of Contents and Print go (their icons stay, the names are kept for screen
                        readers) and "Delete response" says "Delete"; anything still too wide wraps onto a second row. */}
                    <div className="flex min-w-0 flex-wrap items-center gap-1" data-testid="response-actions">
                        {/* only when the list the staff member came from is known (see responseNeighbours) */}
                        {(neighbours.previousId || neighbours.nextId) && (
                            <>
                                <NeighbourLink targetId={neighbours.previousId} href={neighbours.previousId && responsePageUrl(workspace?.workspaceName ?? '', formId, neighbours.previousId)} label={t('RESPONSE_PAGE.PREVIOUS')} icon={<ChevronLeft className="h-4 w-4" aria-hidden="true" />} />
                                {neighbours.position && neighbours.total && (
                                    <span className="px-1 text-sm whitespace-nowrap text-black-700 tabular-nums" data-testid="response-position">
                                        <span className="sr-only">{t('RESPONSE_PAGE.POSITION_SR')}</span>{' '}
                                        {t('RESPONSE_PAGE.POSITION', { position: neighbours.position, total: neighbours.total })}
                                    </span>
                                )}
                                <NeighbourLink targetId={neighbours.nextId} href={neighbours.nextId && responsePageUrl(workspace?.workspaceName ?? '', formId, neighbours.nextId)} label={t('RESPONSE_PAGE.NEXT')} icon={<ChevronRight className="h-4 w-4" aria-hidden="true" />} />
                            </>
                        )}
                        {hasContents && (
                            <a
                                href={`#${CONTENTS_ID}`}
                                onClick={(event) => followInPageLink(event, CONTENTS_ID, CONTENTS_HEADING_ID)}
                                title={t('RESPONSE_PAGE.CONTENTS')}
                                className="flex h-9 min-w-9 items-center justify-center gap-1.5 rounded-md px-2 text-sm font-medium text-black-700 hover:bg-black-200 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500"
                            >
                                <ListOrdered className="h-4 w-4 shrink-0" aria-hidden="true" />
                                <span className="sr-only sm:not-sr-only">{t('RESPONSE_PAGE.CONTENTS')}</span>
                            </a>
                        )}
                        {loaded && can(WorkspacePermission.RESPONSE_READ) && <ResponsePdfButton workspaceId={workspaceId} responseId={response.responseId} formTitle={formTitle} />}
                        {loaded && (
                            <Button variant="ghost" className="min-w-9 px-2!" title={t('RESPONSE_PAGE.PRINT')} onClick={() => window.print()}>
                                <Printer className="h-4 w-4 shrink-0 sm:mr-1.5" aria-hidden="true" />
                                <span className="sr-only sm:not-sr-only">{t('RESPONSE_PAGE.PRINT')}</span>
                            </Button>
                        )}
                        {loaded && canDelete && (
                            <Button variant="dangerGhost" className="px-2!" aria-label={t('RESPONSE_PAGE.DELETE_RESPONSE')} onClick={() => openModal('DELETE_RESPONSE', { workspace, formId, responseId: response.responseId, navigateTo: listUrl, onDeleting: (active: boolean) => setFrozen(active ? fetched : null) })}>
                                <DeleteIcon className="mr-1.5 h-4 w-4 shrink-0 text-[#C43D3D]" aria-hidden="true" />
                                {/* "Delete" at phone width; the button's name is always the whole "Delete response" */}
                                <span aria-hidden="true" className="sm:hidden">
                                    {t('RESPONSE_PAGE.DELETE')}
                                </span>
                                <span aria-hidden="true" className="hidden sm:inline">
                                    {t('RESPONSE_PAGE.DELETE_RESPONSE')}
                                </span>
                            </Button>
                        )}
                    </div>
                </nav>
            </header>

            {failure ? (
                <main>
                    <FailureState failure={failure} listUrl={listUrl} listName={listName} onRetry={() => refetch()} />
                </main>
            ) : !loaded ? (
                <main>
                    <LoadingState />
                </main>
            ) : (
                <>
                    <ResponseSummary
                        ref={detailsRef}
                        response={response}
                        position={neighbours.position && neighbours.total ? { position: neighbours.position, total: neighbours.total } : undefined}
                        // the version it was given in opens read-only (the Versions page: form.read, behind its switch)
                        versionHref={formRevisionsUiEnabled && can(WorkspacePermission.FORM_READ) && typeof response.formVersion === 'number' ? formVersionUrl(workspace?.workspaceName ?? '', formId, response.formVersion) : undefined}
                    />
                    {(response.unreadableFields ?? []).length > 0 && (
                        <div className={`${pageGutter} pb-5`}>
                            <UnreadableNotice unreadable={response.unreadableFields ?? []} />
                        </div>
                    )}
                    <ReadOnlyForm form={form} response={response} />
                    {(!!currentData?.feedback || staffFields.length > 0) && (
                        <section aria-label={t('RESPONSE_PAGE.TEAM_ONLY')} className={`mx-auto flex w-full max-w-2xl flex-col gap-8 px-5 py-10 sm:px-8 print:hidden`}>
                            {currentData?.feedback && (
                                <RespondentFeedbackPanel
                                    key={`feedback-${response.responseId}`}
                                    workspaceId={workspaceId}
                                    formId={formId}
                                    responseId={response.responseId}
                                    feedback={currentData.feedback}
                                    enabled={!!form.settings?.respondentFeedbackEnabled}
                                    statuses={form.settings?.feedbackStatuses ?? []}
                                />
                            )}
                            {staffFields.length > 0 && <InternalFieldsPanel key={`internal-${response.responseId}`} fields={staffFields} response={response} formId={formId} workspaceId={workspaceId} />}
                        </section>
                    )}
                </>
            )}
        </div>
    );
}

/** A previous/next arrow: a real link when the cached list knows the neighbour, else a disabled button. */
function NeighbourLink({ targetId, href, label, icon }: { targetId?: string; href?: string | false | null; label: string; icon: React.ReactNode }) {
    const announce = (event: React.MouseEvent<HTMLAnchorElement>) => {
        // a new tab or window (ctrl/cmd/shift/alt, or not the main button) leaves this page as it is
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        focusDetailsOf = targetId ?? null;
    };
    const classes = 'focus-visible:ring-brand-500 flex h-9 w-9 items-center justify-center rounded-md focus:outline-hidden focus-visible:ring-2';
    if (!href) {
        return (
            <button type="button" disabled aria-label={label} className={`${classes} cursor-default text-black-400`}>
                {icon}
            </button>
        );
    }
    return (
        <Link href={href} aria-label={label} title={label} onClick={announce} className={`${classes} text-black-700 hover:bg-black-200`}>
            {icon}
        </Link>
    );
}

/**
 * Who answered, when (full local time with the zone) and the start of the
 * receipt number. Focusable from script only: previous/next move focus here.
 */
const ResponseSummary = forwardRef<HTMLElement, { response: any; position?: { position: number; total: number }; versionHref?: string }>(function ResponseSummary({ response, position, versionHref }, ref) {
    const { t, i18n } = useTranslation();
    // The receipt number is a bearer token (anyone holding it can read the
    // response without signing in): shortened, never in full on screen,
    // in a tooltip, on the clipboard or in the URL.
    const number: string | undefined = response?.submissionUuid;
    return (
        <section ref={ref} tabIndex={-1} aria-labelledby="rp-details-heading" className={`${pageGutter} py-6 focus:outline-hidden`}>
            <h2 id="rp-details-heading" className="sr-only">
                {position ? t('RESPONSE_PAGE.DETAILS_POSITION', position) : t('RESPONSE_PAGE.DETAILS')}
            </h2>
            <dl className="flex flex-wrap items-start gap-x-10 gap-y-4">
                <div className="flex min-w-0 flex-col gap-1">
                    <dt className="text-xs font-medium text-black-600">{t('RESPONSE_PAGE.RESPONDER')}</dt>
                    <dd className="flex min-w-0 items-center text-base font-medium text-black-900">{response?.dataOwnerIdentifier ? <span className="truncate [overflow-wrap:anywhere]">{response.dataOwnerIdentifier}</span> : <AnonymousBadge />}</dd>
                </div>
                <div className="flex flex-col gap-1">
                    <dt className="text-xs font-medium text-black-600">{t('RESPONSE_PAGE.SUBMITTED')}</dt>
                    <dd className="text-base text-black-900">{utcToLocalDateTimeWithZone(response?.createdAt, undefined, i18n.language)}</dd>
                </div>
                {number && (
                    <div className="flex flex-col gap-1">
                        <dt className="text-xs font-medium text-black-600">{t('RESPONSE_PAGE.RECEIPT')}</dt>
                        <dd className="font-mono text-base text-black-700">{shortReceiptNumber(number)}</dd>
                    </div>
                )}
                {typeof response?.formVersion === 'number' && (
                    <div className="flex flex-col gap-1">
                        <dt className="text-xs font-medium text-black-600">{t('RESPONSE_PAGE.FORM_VERSION')}</dt>
                        <dd className="text-base text-black-900">
                            {versionHref ? (
                                <Link href={versionHref} className="underline underline-offset-2" aria-label={t('RESPONSE_PAGE.FORM_VERSION_LINK', { n: response.formVersion })}>
                                    {t('RESPONSE_PAGE.VERSION_N', { n: response.formVersion })}
                                </Link>
                            ) : (
                                t('RESPONSE_PAGE.VERSION_N', { n: response.formVersion })
                            )}
                        </dd>
                    </div>
                )}
                {response?.deletionStatus === 'pending' && (
                    <div className="flex flex-col gap-1">
                        <dt className="text-xs font-medium text-black-600">{t('RESPONSE_PAGE.DELETION')}</dt>
                        <dd className="text-base text-black-900">{t('RESPONSE_PAGE.DELETION_REQUESTED')}</dd>
                    </div>
                )}
            </dl>
        </section>
    );
});

function LoadingState() {
    const { t } = useTranslation();
    return (
        <div role="status" aria-live="polite" className={`${pageGutter} py-10`}>
            <p className="text-sm text-black-700">{t('RESPONSE_PAGE.LOADING')}</p>
            <div className="mt-6 flex max-w-2xl animate-pulse flex-col gap-6" aria-hidden="true">
                {[0, 1, 2].map((row) => (
                    <div key={row} className="flex flex-col gap-2">
                        <div className="h-4 w-1/3 rounded bg-black-200" />
                        <div className="h-12 w-full rounded bg-black-200" />
                    </div>
                ))}
            </div>
        </div>
    );
}

function FailureState({ failure, listUrl, listName, onRetry }: { failure: ReturnType<typeof failureOf>; listUrl: string; listName: string; onRetry: () => void }) {
    const { t } = useTranslation();
    return (
        <div role="alert" className={`${pageGutter} py-16`}>
            <div className="mx-auto flex max-w-xl flex-col gap-3 rounded-lg border border-black-300 p-6">
                <h1 className="text-lg font-semibold">{t(failure.title)}</h1>
                <p className="text-sm text-black-700">{t(failure.detail)}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                    {failure.kind === 'error' && (
                        <Button variant="primary" onClick={onRetry}>
                            {t('RESPONSE_PAGE.RETRY')}
                        </Button>
                    )}
                    <Link href={listUrl} className="inline-flex min-h-9 items-center rounded px-2 text-sm font-medium text-brand-500 underline underline-offset-2">
                        {t('RESPONSE_PAGE.BACK_TO', { list: listName.toLowerCase() })}
                    </Link>
                </div>
            </div>
        </div>
    );
}

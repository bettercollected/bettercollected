"use client";
import { Shield as ShieldIcon } from 'lucide-react';

import { StandardFormResponseDto } from '@app/models/dtos/form';
import { utcToLocalDateIn, utcToLocalDateTimeIn } from '@app/utils/date-utils';
import { portalPath } from '@app/utils/portal-path';
import { respondentLangQuery } from '@app/utils/respondent-lang-query';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import FeedbackStatusChip from '@Components/form/feedback-status-chip';
import { PortalAudience, usePortalText } from '@app/lib/hooks/use-respondent-language';


interface IWorkspaceFormResponseDeletionCardProps {
    response: StandardFormResponseDto;
    deletionRequests?: boolean;
    className?: string;
    isCustomDomain?: boolean;
    workspaceName: string;
    /** In the respondent's language on the portal, in the app's on the team's dashboard. */
    audience?: PortalAudience;
}

const DECLINE_REASONS = ['legal_obligation', 'legal_claims', 'public_interest', 'identity_not_verified', 'other'];

/**
 * What a deletion request's status means for the respondent. Only `success`
 * says "Deleted": a declined request was NOT deleted and says why (a fixed
 * reason code from the workspace, never free text). Unknown statuses are not
 * shown as deleted either.
 */
export function deletionStatusLabel(status: string, declineReason: string | null | undefined, deletedAt: string, t: (key: string, options?: any) => string): string {
    if (status === 'success') return t('DELETION.DELETED', { date: deletedAt });
    if (status === 'declined') {
        const reason = DECLINE_REASONS.includes(declineReason ?? '') ? (declineReason as string) : 'other';
        return t('DELETION.DECLINED', { reason: t(`DELETION.REASON.${reason.toUpperCase()}`) });
    }
    return t('DELETION.REQUESTED');
}

// Drop the href a Link would take — spreading href="" onto the div trips
// React's empty-href warning.
const DefaultDiv = ({ href, ...props }: any) => <div {...props} />;

/**
 * A submission receipt. Its whole job is to let a responder pick THEIR
 * response out of a list — so it must carry what identifies one: the
 * submission number, the exact time, and whether it was anonymous. (It used
 * to show only the form title and a date, so three submissions to the same
 * form were indistinguishable.)
 */
export default function WorkspaceFormResponseDeletionCard({ response, deletionRequests = false, className = '', workspaceName, isCustomDomain = false, audience = 'team' }: IWorkspaceFormResponseDeletionCardProps) {
    const { t, language } = usePortalText(audience);
    const deletedAt = utcToLocalDateIn(response.updatedAt, language);
    // A ?lang= chosen on the portal carries on to the submission's page.
    const lang = useSearchParams()?.get('lang');
    const langQuery = audience === 'respondent' ? respondentLangQuery(lang) : '';

    const disabled = deletionRequests && response.status === 'success';

    const Component = disabled ? DefaultDiv : Link;

    // Link straight to the default tab: the bare id route only server-redirects
    // to /form, which showed as a URL hop + reload flicker on every open.
    const pathname = disabled ? '' : `${portalPath(workspaceName, isCustomDomain, 'submissions', response.responseId, 'form')}${langQuery}`;

    const isAnonymous = !response?.dataOwnerIdentifier;

    return (
        <Component
            href={pathname}
            className={`relative flex flex-col items-start justify-between h-full bg-white border border-black-300 ${disabled ? 'opacity-60 text-black-600!' : 'hover:border-brand-500'
                } rounded ${className}`}
        >
            <div className="rounded w-full px-5 py-4 flex flex-col gap-3 items-start justify-between">
                <div className="flex w-full flex-wrap items-center justify-between gap-2">
                    {/* An h3 under the tab's h2, so screen-reader users can jump from receipt to receipt. */}
                    {response?.formTitle ? (
                        <h3 className="text-black-800 font-medium">{response.formTitle}</h3>
                    ) : (
                        <h3 className="text-black-800 font-medium" lang={language}>
                            {t('PORTAL.UNTITLED_FORM')}
                        </h3>
                    )}
                    {response?.submissionUuid && (
                        // Mono per the design language: precise, sensitive identifiers.
                        <span className="bg-black-100 text-black-700 rounded px-2 py-0.5 font-mono text-xs" title={t('SUBMISSIONS.NUMBER_TITLE')}>
                            #{response.submissionUuid}
                        </span>
                    )}
                </div>
                <div className="text-black-600 text-sm flex items-center gap-2 flex-wrap" lang={language}>
                    <span>{t(deletionRequests ? 'SUBMISSIONS.REQUESTED' : 'SUBMISSIONS.SUBMITTED', { date: utcToLocalDateTimeIn(response.createdAt, language) })}</span>
                    {isAnonymous && (
                        <span className="flex items-center gap-1 rounded-full bg-[#E7F4EE] px-2 py-0.5 text-xs font-medium text-success-700" title={t('SUBMISSIONS.ANONYMOUS_TITLE')}>
                            <ShieldIcon className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
                            {t('SUBMISSIONS.ANONYMOUS')}
                        </span>
                    )}
                    {!deletionRequests && response?.feedback?.currentStatus && (
                        <span title={t('SUBMISSIONS.LATEST_STATUS_TITLE')}>
                            <FeedbackStatusChip status={response.feedback.currentStatus} />
                        </span>
                    )}
                    {!!response?.status && (
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${response?.status === 'pending' ? 'bg-brand-accent-100 text-brand-olive' : 'bg-black-100 text-black-600'}`}>
                            {deletionStatusLabel(response.status, response.declineReason, deletedAt, t)}
                        </span>
                    )}
                </div>
            </div>
        </Component>
    );
}

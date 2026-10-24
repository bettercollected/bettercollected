'use client';

import FeedbackStatusChip from '@Components/form/feedback-status-chip';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { RespondentFeedbackView } from '@app/models/dtos/form';
import { utcToLocalDateTimeIn } from '@app/utils/date-utils';
import { feedbackAuthor } from '@app/utils/respondent-feedback';

/**
 * "Response from <organisation>": what the team told the respondent about
 * their submission — the current status and every update with its date. The
 * organisation is the author; staff names never reach this page. Its own
 * words are in the respondent's language (and marked so); the team's
 * statuses and messages stay as they wrote them.
 */
export default function RespondentFeedbackSection({ feedback, workspaceTitle }: { feedback?: RespondentFeedbackView | null; workspaceTitle?: string | null }) {
    const { t, language } = useRespondentLanguage();
    if (!feedback) return null;
    const entries = feedback.entries ?? [];
    const author = feedbackAuthor(feedback.author, workspaceTitle);

    return (
        <section aria-labelledby="respondent-feedback-heading" className="mt-6 flex flex-col gap-3 rounded-lg border border-black-400 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 id="respondent-feedback-heading" className="text-sm font-semibold text-black-900" lang={language}>
                    {t('FEEDBACK.RESPONSE_FROM', { author })}
                </h2>
                {feedback.currentStatus && <FeedbackStatusChip status={feedback.currentStatus} />}
            </div>
            {entries.length === 0 ? (
                <span className="text-sm text-black-600" lang={language}>
                    {t('FEEDBACK.NO_UPDATES')}
                </span>
            ) : (
                <ol className="flex flex-col gap-3">
                    {[...entries].reverse().map((entry, index) => (
                        <li key={`${entry.createdAt}-${index}`} className="flex flex-col gap-1 border-l-2 border-black-300 pl-3">
                            <span className="text-xs text-black-600">{utcToLocalDateTimeIn(entry.createdAt, language)}</span>
                            {entry.status && (
                                <span className="text-sm text-black-700">
                                    <span lang={language}>{t('FEEDBACK.STATUS')}:</span> <FeedbackStatusChip status={entry.status} />
                                </span>
                            )}
                            {entry.message && <p className="text-sm leading-relaxed wrap-break-word whitespace-pre-wrap text-black-900">{entry.message}</p>}
                        </li>
                    ))}
                </ol>
            )}
        </section>
    );
}

'use client';

import FeedbackStatusChip from '@Components/form/feedback-status-chip';

import { RespondentFeedbackView } from '@app/models/dtos/form';
import { utcToLocalDateTIme } from '@app/utils/date-utils';
import { feedbackAuthor } from '@app/utils/respondent-feedback';

/**
 * "Response from <organisation>": what the team told the respondent about
 * their submission — the current status and every update with its date. The
 * organisation is the author; staff names never reach this page.
 */
export default function RespondentFeedbackSection({ feedback, workspaceTitle }: { feedback?: RespondentFeedbackView | null; workspaceTitle?: string | null }) {
    if (!feedback) return null;
    const entries = feedback.entries ?? [];
    const author = feedbackAuthor(feedback.author, workspaceTitle);

    return (
        <section aria-labelledby="respondent-feedback-heading" className="mt-6 flex flex-col gap-3 rounded-lg border border-black-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <span id="respondent-feedback-heading" className="text-sm font-semibold text-black-900">
                    Response from {author}
                </span>
                {feedback.currentStatus && <FeedbackStatusChip status={feedback.currentStatus} />}
            </div>
            {entries.length === 0 ? (
                <span className="text-sm text-black-600">No updates yet. Check back here later.</span>
            ) : (
                <ol className="flex flex-col gap-3">
                    {[...entries].reverse().map((entry, index) => (
                        <li key={`${entry.createdAt}-${index}`} className="flex flex-col gap-1 border-l-2 border-black-200 pl-3">
                            <span className="text-xs text-black-500">{utcToLocalDateTIme(entry.createdAt)}</span>
                            {entry.status && (
                                <span className="text-sm text-black-700">
                                    Status: <FeedbackStatusChip status={entry.status} />
                                </span>
                            )}
                            {entry.message && <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-black-900">{entry.message}</p>}
                        </li>
                    ))}
                </ol>
            )}
        </section>
    );
}

'use client';

import { useState } from 'react';

import FeedbackStatusChip from '@Components/form/feedback-status-chip';
import { MessageSquareText } from 'lucide-react';

import { StaffFeedback } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { usePostRespondentFeedbackMutation } from '@app/store/workspaces/api';
import { utcToLocalDateTIme } from '@app/utils/date-utils';
import { MAX_FEEDBACK_MESSAGE_LENGTH, canSendFeedback } from '@app/utils/respondent-feedback';
import { selectClass } from '@app/views/molecules/form-builder/condition-editor-shared';

interface RespondentFeedbackPanelProps {
    workspaceId: string;
    formId: string;
    responseId: string;
    /** The staff view from the submission endpoint (members only). */
    feedback?: StaffFeedback | null;
    /** The form's "Respond to submissions" setting and its statuses. */
    enabled?: boolean;
    statuses?: string[];
}

/**
 * The team's updates to the respondent of one submission ("Selected", "We
 * need one more document"): the history with who posted each, and — for
 * workspace admins and the owner — a composer. Unlike internal fields, the
 * respondent sees these updates (without the staff member's name).
 */
export default function RespondentFeedbackPanel({ workspaceId, formId, responseId, feedback, enabled = false, statuses = [] }: RespondentFeedbackPanelProps) {
    const { toast } = useToast();
    const [postFeedback, { isLoading }] = usePostRespondentFeedbackMutation();
    const [state, setState] = useState<StaffFeedback>(feedback ?? {});
    const [status, setStatus] = useState('');
    const [message, setMessage] = useState('');

    const entries = state.entries ?? [];
    if (!enabled && entries.length === 0) return null;
    const canPost = enabled && !!state.canPost;

    const send = async () => {
        const result: any = await postFeedback({ workspaceId, formId, responseId, status: status || null, message: message.trim() || null });
        if (result?.data) {
            setState(result.data);
            setStatus('');
            setMessage('');
            toast({ description: result.data.notifiesRespondent ? 'Update sent. The respondent will get an email notice.' : 'Update saved for the respondent.' });
        } else {
            const detail = result?.error?.data;
            const text = typeof detail === 'string' ? detail : typeof detail?.message === 'string' ? detail.message : typeof detail?.detail === 'string' ? detail.detail : null;
            toast({ description: text || 'Could not send the update', variant: 'destructive' });
        }
    };

    return (
        <section aria-labelledby="respondent-feedback-heading" className="flex flex-col gap-4 rounded-lg border border-black-200 bg-white p-4">
            <div className="flex flex-col gap-0.5">
                <span id="respondent-feedback-heading" className="flex items-center gap-1.5 text-sm font-semibold text-black-800">
                    <MessageSquareText className="h-3.5 w-3.5" aria-hidden="true" />
                    Response to the respondent
                    {state.currentStatus && <FeedbackStatusChip status={state.currentStatus} />}
                </span>
                <span className="text-xs text-black-600">The respondent sees these updates, signed with your organisation&apos;s name.</span>
            </div>

            {entries.length > 0 ? (
                <ol className="flex flex-col gap-3" aria-label="Updates sent">
                    {entries.map((entry, index) => (
                        <li key={entry.id ?? index} className="flex flex-col gap-1 border-l-2 border-black-200 pl-3">
                            {entry.status && <FeedbackStatusChip status={entry.status} />}
                            {entry.message && <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-black-900">{entry.message}</p>}
                            <span className="text-[11px] text-black-500">
                                {entry.createdByEmail || 'A team member'} · {utcToLocalDateTIme(entry.createdAt)}
                            </span>
                        </li>
                    ))}
                </ol>
            ) : (
                <span className="text-sm italic text-black-500">No updates yet</span>
            )}

            {canPost && (
                <div className="flex flex-col gap-2">
                    <label htmlFor={`feedback-status-${responseId}`} className="text-[13px] font-medium text-black-700">
                        Status
                    </label>
                    <select id={`feedback-status-${responseId}`} className={selectClass} value={status} onChange={(e) => setStatus(e.target.value)}>
                        <option value="">No status change</option>
                        {statuses.map((option) => (
                            <option key={option} value={option}>
                                {option}
                            </option>
                        ))}
                    </select>
                    <label htmlFor={`feedback-message-${responseId}`} className="text-[13px] font-medium text-black-700">
                        Message
                    </label>
                    <Textarea id={`feedback-message-${responseId}`} className="min-h-[88px] text-sm" maxLength={MAX_FEEDBACK_MESSAGE_LENGTH} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Optional note for the respondent" />
                    <span className="text-[11px] text-black-500">
                        {state.notifiesRespondent ? 'The respondent gets an email that there is an update, with a link — never the update itself.' : 'The respondent is not emailed: they see this on their submission page, with their submission number.'}
                    </span>
                    <div className="flex justify-end">
                        <Button variant="primary" size="sm" isLoading={isLoading} disabled={!canSendFeedback(status, message) || isLoading} onClick={send}>
                            Send update
                        </Button>
                    </div>
                </div>
            )}
            {enabled && !canPost && <span className="text-[11px] text-black-500">Your role can read updates but not send them.</span>}
        </section>
    );
}

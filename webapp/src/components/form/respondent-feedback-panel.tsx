'use client';

import { useState } from 'react';

import FeedbackStatusChip from '@Components/form/feedback-status-chip';
import { MessageSquareText } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { StaffFeedback } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { usePostRespondentFeedbackMutation } from '@app/store/workspaces/api';
import { utcToLocalDateTimeIn } from '@app/utils/date-utils';
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
    const { t, i18n } = useTranslation();
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
            toast({ description: t(result.data.notifiesRespondent ? 'RESPONSE_TEAM.FEEDBACK_SENT_NOTIFIED' : 'RESPONSE_TEAM.FEEDBACK_SENT') });
        } else {
            const detail = result?.error?.data;
            const text = typeof detail === 'string' ? detail : typeof detail?.message === 'string' ? detail.message : typeof detail?.detail === 'string' ? detail.detail : null;
            toast({ description: text || t('RESPONSE_TEAM.FEEDBACK_FAILED'), variant: 'destructive' });
        }
    };

    return (
        <section aria-labelledby="respondent-feedback-heading" className="flex flex-col gap-4 rounded border border-black-300 bg-white p-4">
            <div className="flex flex-col gap-0.5">
                <span id="respondent-feedback-heading" className="flex items-center gap-1.5 text-sm font-semibold text-black-800">
                    <MessageSquareText className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('RESPONSE_TEAM.FEEDBACK_TITLE')}
                    {state.currentStatus && <FeedbackStatusChip status={state.currentStatus} />}
                </span>
                <span className="text-xs text-black-600">{t('RESPONSE_TEAM.FEEDBACK_NOTE')}</span>
            </div>

            {entries.length > 0 ? (
                <ol className="flex flex-col gap-3" aria-label={t('RESPONSE_TEAM.FEEDBACK_LIST')}>
                    {entries.map((entry, index) => (
                        <li key={entry.id ?? index} className="flex flex-col gap-1 border-l-2 border-black-300 pl-3">
                            {entry.status && <FeedbackStatusChip status={entry.status} />}
                            {entry.message && <p className="whitespace-pre-wrap wrap-break-word text-sm leading-relaxed text-black-900">{entry.message}</p>}
                            <span className="text-[11px] text-black-600">
                                {entry.createdByEmail || t('RESPONSE_TEAM.TEAM_MEMBER')} · {utcToLocalDateTimeIn(entry.createdAt, i18n.language)}
                            </span>
                        </li>
                    ))}
                </ol>
            ) : (
                <span className="text-sm italic text-black-600">{t('RESPONSE_TEAM.FEEDBACK_NONE')}</span>
            )}

            {canPost && (
                <div className="flex flex-col gap-2">
                    <label htmlFor={`feedback-status-${responseId}`} className="text-[13px] font-medium text-black-700">
                        {t('RESPONSE_TEAM.FEEDBACK_STATUS')}
                    </label>
                    <select id={`feedback-status-${responseId}`} className={selectClass} value={status} onChange={(e) => setStatus(e.target.value)}>
                        <option value="">{t('RESPONSE_TEAM.FEEDBACK_NO_CHANGE')}</option>
                        {statuses.map((option) => (
                            <option key={option} value={option}>
                                {option}
                            </option>
                        ))}
                    </select>
                    <label htmlFor={`feedback-message-${responseId}`} className="text-[13px] font-medium text-black-700">
                        {t('RESPONSE_TEAM.FEEDBACK_MESSAGE')}
                    </label>
                    <Textarea id={`feedback-message-${responseId}`} className="min-h-[88px] text-sm" maxLength={MAX_FEEDBACK_MESSAGE_LENGTH} value={message} onChange={(e) => setMessage(e.target.value)} placeholder={t('RESPONSE_TEAM.FEEDBACK_PLACEHOLDER')} />
                    <span className="text-[11px] text-black-600">
                        {t(state.notifiesRespondent ? 'RESPONSE_TEAM.FEEDBACK_NOTIFIES' : 'RESPONSE_TEAM.FEEDBACK_NOT_NOTIFIED')}
                    </span>
                    <div className="flex justify-end">
                        <Button variant="primary" size="sm" isLoading={isLoading} disabled={!canSendFeedback(status, message) || isLoading} onClick={send}>
                            {t('RESPONSE_TEAM.FEEDBACK_SEND')}
                        </Button>
                    </div>
                </div>
            )}
            {enabled && !canPost && <span className="text-[11px] text-black-600">{t('RESPONSE_TEAM.FEEDBACK_READ_ONLY')}</span>}
        </section>
    );
}

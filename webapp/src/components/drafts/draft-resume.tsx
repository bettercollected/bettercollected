'use client';

import { useEffect, useRef, useState } from 'react';

import { X } from 'lucide-react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useRespondentDraft } from '@app/store/jotai/respondent-draft';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { OpenedDraft, UnavailableDraft, isUnavailableDraft, useDiscardDraftMutation, useGetMyDraftMutation, useOpenDraftMutation } from '@app/store/redux/drafts-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { formatDraftDate, restoreDraft } from '@app/utils/form-drafts';

type Notice = { kind: 'restored'; date?: string } | { kind: 'changed'; dropped: number } | { kind: 'unavailable'; reason: UnavailableDraft['unavailable']; date?: string } | { kind: 'not_found' } | { kind: 'failed' };

/**
 * Picks a saved draft up when the respondent comes back: from the link in the
 * address (`#resume=<token>`, read once and removed from the address bar), or,
 * signed in, from their account. Puts the answers, the hidden-field values and
 * the page they were on back, says what happened in a note above the form, and
 * says so when the form changed, closed or filled since. Renders nothing for a
 * form that keeps no drafts.
 */
export default function DraftResume({ form, token: linkToken }: { token?: string | null; form?: Pick<StandardFormDto, 'formId' | 'fields' | 'hiddenFields' | 'settings'> }) {
    const { t, language } = useRespondentLanguage();
    const workspace = useAppSelector(selectWorkspace);
    const shown = useAppSelector(selectResponderForm);
    const auth = useAppSelector(selectAuth);
    const { setFormResponse } = useFormResponse();
    const { setHiddenValues } = useHiddenFieldValues();
    const { setResponderState } = useResponderState();
    const { setDraft } = useRespondentDraft(form?.formId);
    const [openDraft] = useOpenDraftMutation();
    const [getMyDraft] = useGetMyDraftMutation();
    const [discardDraft, { isLoading: deleting }] = useDiscardDraftMutation();
    const [notice, setNotice] = useState<Notice | null>(null);
    // The link's token, taken from the address bar by the page as it started
    // (utils/form-drafts.ts takeResumeToken) and kept here only to open or delete this draft.
    const token = useRef<string | null>(linkToken ?? null);
    if (linkToken && !token.current) token.current = linkToken;
    const started = useRef({ link: false, account: false });

    const enabled = !!form?.settings?.allowSaveDraft && !!form?.formId;
    const ready = enabled && !!workspace?.id && shown?.formId === form?.formId;
    const signedIn = !!auth?.id;

    const apply = (draft: OpenedDraft | UnavailableDraft) => {
        if (isUnavailableDraft(draft)) {
            setNotice({ kind: 'unavailable', reason: draft.unavailable, date: draft.expiresAt });
            return;
        }
        const restored = restoreDraft(form as StandardFormDto, draft);
        setFormResponse((previous) => ({ ...previous, answers: { ...previous.answers, ...restored.answers } }));
        // what the share link carries now wins over what was saved
        setHiddenValues((current) => ({ ...restored.hiddenFields, ...current }));
        setResponderState((previous) => ({ ...previous, currentSlide: restored.slide, prevActiveSlide: restored.slide, currentField: 0, prevActiveField: -1, history: restored.history }));
        setDraft({ editKey: draft.editKey, expiresAt: draft.expiresAt, status: 'resumed' });
        setNotice(draft.formChanged ? { kind: 'changed', dropped: restored.dropped } : { kind: 'restored', date: draft.savedAt });
    };

    // The link: open the draft it names.
    useEffect(() => {
        if (!ready || started.current.link || !token.current) return;
        started.current.link = true;
        void openDraft({ workspaceId: workspace.id, formId: form!.formId, token: token.current }).then((result) => {
            if ('data' in result && result.data) return apply(result.data);
            const status = (result.error as { status?: number } | undefined)?.status;
            setNotice({ kind: status === 404 ? 'not_found' : 'failed' });
        });
    }, [ready]);

    // Signed in, without a link: the account's own draft, if there is one.
    useEffect(() => {
        if (!ready || !signedIn || started.current.account || token.current) return;
        started.current.account = true;
        void getMyDraft({ workspaceId: workspace.id, formId: form!.formId }).then((result) => {
            // none (404) or a failure: the form simply starts as usual
            if ('data' in result && result.data) apply(result.data);
        });
    }, [ready, signedIn]);

    if (!enabled) return null;

    const remove = async () => {
        const result = await discardDraft({ workspaceId: workspace.id, formId: form!.formId, token: token.current ?? undefined });
        if ('error' in result && (result.error as { status?: number })?.status !== 404) return;
        token.current = null;
        setDraft({ status: 'deleted' });
        setNotice(null);
    };

    const text = !notice
        ? ''
        : (() => {
              switch (notice.kind) {
                  case 'restored':
                      return t('DRAFT.NOTICE.RESTORED', { date: formatDraftDate(notice.date, language) });
                  case 'changed':
                      return `${t('DRAFT.NOTICE.CHANGED')}${notice.dropped > 0 ? ` ${t('DRAFT.NOTICE.DROPPED', { count: notice.dropped })}` : ''}`;
                  case 'unavailable':
                      return t(`DRAFT.NOTICE.UNAVAILABLE_${notice.reason}`, { date: formatDraftDate(notice.date, language) });
                  case 'not_found':
                      return t('DRAFT.NOTICE.NOT_FOUND');
                  default:
                      return t('DRAFT.NOTICE.FAILED');
              }
          })();

    return (
        // The live region is always there, so the note is announced when it comes.
        <div role="status" aria-label={t('DRAFT.NOTICE.LABEL')} lang={language}>
            {notice && (
                <div data-testid="draft-notice" className="relative z-90 shrink-0 border-b border-black-300 bg-white px-4 py-3 text-black-900">
                    <div className="mx-auto flex max-w-[720px] flex-wrap items-center gap-x-4 gap-y-2">
                        <p className="min-w-0 flex-1 text-[15px] leading-relaxed">{text}</p>
                        {notice.kind === 'unavailable' && (
                            <button type="button" onClick={remove} disabled={deleting} className="min-h-11 rounded-[4px] px-2 text-[15px] font-medium underline underline-offset-4 disabled:opacity-60">
                                {t('DRAFT.NOTICE.DELETE_NOW')}
                            </button>
                        )}
                        <button type="button" onClick={() => setNotice(null)} aria-label={t('DRAFT.NOTICE.DISMISS')} className="flex min-h-11 min-w-11 items-center justify-center rounded-[4px]">
                            <X className="h-4 w-4" aria-hidden="true" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

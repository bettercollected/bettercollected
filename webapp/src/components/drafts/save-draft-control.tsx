'use client';

import { FormEvent, useEffect, useId, useRef, useState } from 'react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useRespondentDraft } from '@app/store/jotai/respondent-draft';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { useDiscardDraftMutation, useRequestDraftLinkMutation, useSaveDraftMutation } from '@app/store/redux/drafts-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { DRAFT_LINK_DAYS, answersForDraft, draftErrorKey, draftsOffered, formatDraftDate, hasFileQuestion, hasSignatureQuestion, positionForDraft } from '@app/utils/form-drafts';

/**
 * "Save and continue later" on a question page, when the form lets respondents
 * (settings.allowSaveDraft). Signed in: the draft is saved to the account.
 * Not signed in: the respondent enters an address once and gets a link; the
 * address is used for that mail and not kept. After the first save the page
 * keeps saving with the browser's edit key, so no second mail is needed.
 *
 * Plain controls in the page's own flow (no dialog): the address form opens
 * in place and takes focus; what happened is said in a polite status region,
 * what went wrong in an alert next to the control.
 */
export default function SaveDraftControl({ ink }: { ink?: string }) {
    const { t, language } = useRespondentLanguage();
    const standardForm = useAppSelector(selectResponderForm);
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const signedIn = !!auth?.id;
    const { formResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    const { responderState } = useResponderState();
    const { draft, setDraft, resetDraft } = useRespondentDraft(standardForm?.formId);
    const [saveDraft, { isLoading: saving }] = useSaveDraftMutation();
    const [requestLink, { isLoading: sending }] = useRequestDraftLinkMutation();
    const [discardDraft, { isLoading: deleting }] = useDiscardDraftMutation();
    const [asking, setAsking] = useState(false);
    const [email, setEmail] = useState('');
    const [error, setError] = useState<string | null>(null);
    const emailRef = useRef<HTMLInputElement>(null);
    const saveRef = useRef<HTMLButtonElement>(null);
    const statusRef = useRef<HTMLParagraphElement>(null);
    const ids = { title: useId(), hint: useId(), error: useId() };

    useEffect(() => {
        if (asking) emailRef.current?.focus();
    }, [asking]);

    if (!draftsOffered(standardForm?.settings, signedIn) || !standardForm?.formId || !workspace?.id) return null;

    const key = { workspaceId: workspace.id, formId: standardForm.formId };
    const hasDraft = draft.status !== 'none' && draft.status !== 'deleted';
    const busy = saving || sending || deleting;
    const locale = language === 'nl' ? 'nl' : 'en';
    const content = () => ({
        answers: answersForDraft(standardForm.fields, formResponse.answers),
        hiddenFields: hiddenValues,
        position: positionForDraft(standardForm.fields, responderState.currentSlide, responderState.history),
        formVersion: standardForm.version || undefined
    });
    const when = (iso?: string) => formatDraftDate(iso, language);
    const fail = (failure: unknown) => {
        const message = draftErrorKey(failure);
        setError(message);
        // The key no longer opens a draft (deleted, expired): start over with a link.
        if (message === 'DRAFT.ERR_NOT_FOUND' && !signedIn) resetDraft();
    };

    const save = async () => {
        setError(null);
        const result = await saveDraft({ ...key, body: { ...content(), ...(signedIn ? {} : { editKey: draft.editKey }) } });
        if ('error' in result) return fail(result.error);
        setDraft({ ...draft, status: hasDraft ? 'changes_saved' : 'saved_account', expiresAt: result.data.expiresAt });
    };

    const begin = () => {
        setError(null);
        if (signedIn) void save();
        else setAsking(true);
    };

    const send = async (event: FormEvent) => {
        event.preventDefault();
        setError(null);
        const address = email.trim();
        const result = await requestLink({ ...key, body: { ...content(), email: address, locale, editKey: draft.editKey } });
        if ('error' in result) return fail(result.error);
        setAsking(false);
        setDraft({ editKey: result.data.editKey, email: address, expiresAt: result.data.expiresAt, status: 'link_sent' });
        // The form that held focus is gone: the confirmation takes it.
        setTimeout(() => statusRef.current?.focus(), 0);
    };

    const remove = async () => {
        setError(null);
        const result = await discardDraft({ ...key, editKey: draft.editKey });
        // Nothing left to delete is the same outcome.
        if ('error' in result && (result.error as { status?: number })?.status !== 404) return fail(result.error);
        setDraft({ status: 'deleted' });
        setTimeout(() => statusRef.current?.focus(), 0);
    };

    const status = (() => {
        switch (draft.status) {
            case 'saved_account':
                return t('DRAFT.SAVED_ACCOUNT', { date: when(draft.expiresAt) });
            case 'link_sent':
                return t('DRAFT.LINK_SENT', { email: draft.email, days: DRAFT_LINK_DAYS });
            case 'resumed':
                return t('DRAFT.RESUMED', { date: when(draft.expiresAt) });
            case 'changes_saved':
                return t('DRAFT.CHANGES_SAVED', { date: when(draft.expiresAt) });
            case 'deleted':
                return t('DRAFT.DELETED');
            default:
                return '';
        }
    })();

    const quiet = cn('min-h-11 w-fit rounded-[4px] px-1 text-[15px] font-medium underline underline-offset-4 disabled:cursor-wait disabled:opacity-60');
    const style = ink ? { color: ink } : undefined;

    return (
        <div className="flex w-full max-w-[560px] flex-col items-start gap-2" lang={language} data-testid="save-draft">
            {!asking && !hasDraft && (
                <button ref={saveRef} type="button" className={quiet} style={style} onClick={begin} disabled={busy}>
                    {saving ? t('DRAFT.SAVING') : t('DRAFT.SAVE')}
                </button>
            )}
            {!asking && hasDraft && (
                <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
                    <button type="button" className={quiet} style={style} onClick={save} disabled={busy}>
                        {saving ? t('DRAFT.SAVING') : t('DRAFT.SAVE_CHANGES')}
                    </button>
                    {!signedIn && (
                        <button type="button" className={quiet} style={style} onClick={() => setAsking(true)} disabled={busy}>
                            {t('DRAFT.SEND_AGAIN')}
                        </button>
                    )}
                    <button type="button" className={quiet} style={style} onClick={remove} disabled={busy}>
                        {t('DRAFT.DELETE')}
                    </button>
                </div>
            )}
            {asking && (
                <form onSubmit={send} aria-labelledby={ids.title} className="flex w-full flex-col gap-3 rounded-[8px] border border-black-300 bg-white p-4 text-black-900" noValidate>
                    <h2 id={ids.title} className="text-[15px] font-semibold">
                        {t('DRAFT.EMAIL_TITLE')}
                    </h2>
                    <div className="flex flex-col gap-1.5">
                        <label htmlFor={`${ids.title}-email`} className="text-[15px] font-medium">
                            {t('DRAFT.EMAIL_LABEL')}
                        </label>
                        <input
                            ref={emailRef}
                            id={`${ids.title}-email`}
                            type="email"
                            name="email"
                            autoComplete="email"
                            inputMode="email"
                            required
                            value={email}
                            onChange={(event) => setEmail(event.target.value)}
                            aria-describedby={error ? `${ids.hint} ${ids.error}` : ids.hint}
                            aria-invalid={error === 'DRAFT.ERR_EMAIL' || undefined}
                            className="min-h-12 w-full rounded-[8px] border border-control bg-white px-3 text-base text-black-900"
                        />
                        <p id={ids.hint} className="text-[13px] text-black-700">
                            {t('DRAFT.EMAIL_HINT')}
                        </p>
                    </div>
                    {hasFileQuestion(standardForm.fields) && <p className="text-[13px] text-black-700">{t('DRAFT.FILES_NOTE')}</p>}
                    {hasSignatureQuestion(standardForm.fields) && <p className="text-[13px] text-black-700">{t('DRAFT.SIGNATURE_NOTE')}</p>}
                    <div className="flex flex-wrap items-center gap-3">
                        <button type="submit" disabled={busy || !email.trim()} className="min-h-11 rounded-[8px] bg-black-900 px-5 text-[15px] font-semibold text-white disabled:cursor-wait disabled:opacity-60">
                            {sending ? t('DRAFT.SAVING') : t('DRAFT.SEND')}
                        </button>
                        <button
                            type="button"
                            className={quiet}
                            onClick={() => {
                                setAsking(false);
                                setError(null);
                                setTimeout(() => saveRef.current?.focus(), 0);
                            }}
                        >
                            {t('DRAFT.CANCEL')}
                        </button>
                    </div>
                </form>
            )}
            {!asking && !hasDraft && hasFileQuestion(standardForm.fields) && signedIn && <p className="text-[13px] text-black-700">{t('DRAFT.FILES_NOTE')}</p>}
            {!asking && !hasDraft && hasSignatureQuestion(standardForm.fields) && signedIn && <p className="text-[13px] text-black-700">{t('DRAFT.SIGNATURE_NOTE')}</p>}
            <p ref={statusRef} role="status" tabIndex={-1} className={cn('text-[14px] leading-relaxed text-black-800 outline-none', !status && 'sr-only')}>
                {status}
            </p>
            {error && (
                <p id={ids.error} role="alert" className="text-[15px] leading-relaxed font-medium text-[#B42318]">
                    {t(error)}
                </p>
            )}
        </div>
    );
}

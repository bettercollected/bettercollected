'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import Link from 'next/link';

import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { DialogOverlay, DialogPortal } from '@app/shadcn/components/ui/dialog';
import { type PromotionApplied, type PromotionPreview, type PromotionProblem, useApplyPromotionMutation, usePreviewPromotionMutation } from '@app/store/workspaces/form-promotion-api';

import { PromotionFailureKind, dashboardFormUrl, failureKey, failureOf, isStale, newIdempotencyKey } from './promotion-errors';
import ReviewStep from './review-step';
import { useTargetWorkspaces } from './use-target-workspaces';
import WhereStep, { Mode } from './where-step';

const BUTTON = 'flex min-h-[44px] items-center justify-center rounded px-4 text-sm font-medium disabled:cursor-not-allowed sm:min-h-[36px]';
const PRIMARY = `${BUTTON} bg-action text-white hover:bg-action-hover disabled:bg-black-300 disabled:text-black-600`;
const SECONDARY = `${BUTTON} border border-black-400 bg-white text-black-700 hover:bg-black-200 disabled:bg-black-300 disabled:text-black-600`;

const TOTAL_STEPS = 3;

export interface FormPromotionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** The workspace and form being copied. */
    workspace: WorkspaceDto;
    form: Pick<StandardFormDto, 'formId' | 'title'>;
}

/**
 * "Copy to another workspace": three steps (where to, review, done). The server decides everything on both sides; the
 * dialog shows what it says and never copies without the review it was shown (both ETags go back, a stale one reviews
 * again). Opening it asks nothing while closed; the form menu shows its item only while the server has copying on.
 */
export default function FormPromotionDialog({ open, onOpenChange, workspace, form }: FormPromotionDialogProps) {
    // closed: nothing is mounted, so nothing is asked and the next opening starts over
    if (!open) return null;
    return <Body onOpenChange={onOpenChange} workspace={workspace} form={form} />;
}

function Body({ onOpenChange, workspace, form }: Omit<FormPromotionDialogProps, 'open'>) {
    const { t } = useTranslation();
    const headingRef = useRef<HTMLHeadingElement>(null);
    const { workspaces, loading, failed } = useTargetWorkspaces(true);

    const [step, setStep] = useState<1 | 2 | 3>(1);
    const [targetWorkspaceId, setTargetWorkspaceId] = useState('');
    const [mode, setMode] = useState<Mode>('new');
    const [target, setTarget] = useState<{ id: string; title: string }>({ id: '', title: '' });
    const [copyPrivacy, setCopyPrivacy] = useState(false);
    const [overwrite, setOverwrite] = useState(false);
    const [confirmRetention, setConfirmRetention] = useState(false);

    const [preview, setPreview] = useState<PromotionPreview | null>(null);
    const [previewFailure, setPreviewFailure] = useState<PromotionFailureKind | null>(null);
    const [applyFailure, setApplyFailure] = useState<PromotionFailureKind | null>(null);
    const [applyProblems, setApplyProblems] = useState<PromotionProblem[] | null>(null);
    const [notice, setNotice] = useState<PromotionFailureKind | null>(null);
    const [applied, setApplied] = useState<PromotionApplied | null>(null);

    const [runPreview, previewing] = usePreviewPromotionMutation();
    const [runApply, applying] = useApplyPromotionMutation();
    // one key for one body: the same copy sent again (a double click, a lost answer) is the same copy
    const keyed = useRef<{ body: string; key: string } | null>(null);
    // the latest review request wins: an answer for an older one is ignored
    const latest = useRef(0);

    const targetWorkspace = workspaces.find((w) => w.id === targetWorkspaceId);
    const targetFormId = mode === 'existing' ? target.id : '';
    const accessUrl = targetWorkspace && targetFormId ? dashboardFormUrl(targetWorkspace.workspaceName, targetFormId, '/settings/access') : undefined;
    const busy = previewing.isLoading || applying.isLoading;

    const canContinue = !!targetWorkspace && (mode === 'new' || !!targetFormId);

    const review = useCallback(
        async (privacy: boolean, then?: PromotionFailureKind | null) => {
            if (!targetWorkspaceId) return;
            const call = ++latest.current;
            setPreviewFailure(null);
            setApplyFailure(null);
            setApplyProblems(null);
            try {
                const result = await runPreview({
                    workspaceId: workspace.id,
                    formId: form.formId,
                    targetWorkspaceId,
                    targetFormId: mode === 'existing' && target.id ? target.id : null,
                    copyDataProtection: privacy
                }).unwrap();
                if (call !== latest.current) return;
                setPreview(result);
                keyed.current = null;
                setNotice(then ?? null);
            } catch (error) {
                if (call !== latest.current) return;
                setPreview(null);
                setPreviewFailure(failureOf(error).kind);
            }
        },
        [runPreview, workspace.id, form.formId, targetWorkspaceId, mode, target.id]
    );

    // each step has a heading that takes focus when it arrives: the person hears where they are
    useEffect(() => {
        headingRef.current?.focus();
    }, [step]);

    const goReview = () => {
        setStep(2);
        setPreview(null);
        setNotice(null);
        setOverwrite(false);
        setConfirmRetention(false);
        setCopyPrivacy(false);
        void review(false);
    };

    const changePrivacy = (value: boolean) => {
        setCopyPrivacy(value);
        setConfirmRetention(false);
        void review(value);
    };

    const retentionAsk = !!preview?.retentionShortened || applyFailure === 'retention_confirmation_required';
    const problems: PromotionProblem[] = applyProblems ?? preview?.errors ?? [];
    const needsOverwrite = !!preview?.targetChangedSinceLastPromotion && mode === 'existing';
    const ready = !!preview && preview.valid && !busy && (!needsOverwrite || overwrite) && (!(copyPrivacy && retentionAsk) || confirmRetention) && !problems.some((p) => p.code === 'target_not_restricted');

    const copy = async () => {
        if (!preview || !targetWorkspaceId) return;
        const body = {
            workspaceId: workspace.id,
            formId: form.formId,
            targetWorkspaceId,
            targetFormId: mode === 'existing' && target.id ? target.id : null,
            copyDataProtection: copyPrivacy,
            sourceEtag: preview.sourceEtag,
            targetEtag: preview.targetEtag ?? null,
            overwrite: needsOverwrite && overwrite,
            confirmShorterRetention: copyPrivacy && retentionAsk && confirmRetention
        };
        const fingerprint = JSON.stringify(body);
        setApplyFailure(null);
        setApplyProblems(null);
        setNotice(null);
        try {
            if (keyed.current?.body !== fingerprint) keyed.current = { body: fingerprint, key: newIdempotencyKey() };
            const result = await runApply({ ...body, idempotencyKey: keyed.current.key }).unwrap();
            setApplied(result);
            setStep(3);
        } catch (error) {
            const failure = failureOf(error);
            if (isStale(failure.kind)) {
                // what was reviewed is not what is there any more: look again, and say so
                await review(copyPrivacy, 'precondition_failed');
                return;
            }
            setApplyFailure(failure.kind);
            if (failure.kind === 'invalid_spec' && failure.problems.length > 0) setApplyProblems(failure.problems);
            if (failure.kind === 'target_not_restricted') {
                // the form's mode is not what the review saw: the next review says it as an error
                setApplyProblems([{ path: '/targetFormId', code: 'target_not_restricted', message: '' }]);
            }
        }
    };

    const stepName = step === 1 ? 'STEP_WHERE' : step === 2 ? 'STEP_REVIEW' : 'STEP_DONE';
    const sourceTitle = form.title || '';

    return (
        // Events of a portal bubble through the React tree: the form cards and rows this is opened from are clickable, and a click in the dialog must not open them.
        <div className="contents" onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
            <DialogPrimitive.Root open onOpenChange={onOpenChange}>
                <DialogPortal>
                    <DialogOverlay />
                    <DialogPrimitive.Content
                        data-testid="form-promotion-dialog"
                        aria-describedby="promotion-lead"
                        onOpenAutoFocus={(event: Event) => {
                            // the step heading, not the first control: the dialog is announced from its title, then the step
                            event.preventDefault();
                            headingRef.current?.focus();
                        }}
                        className="fixed inset-x-0 bottom-0 z-modal flex max-h-[92dvh] w-full flex-col rounded-t-lg border border-black-300 bg-white shadow-large sm:inset-x-auto sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:max-h-[88dvh] sm:max-w-[640px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded"
                    >
                        <div className="flex items-start justify-between gap-4 border-b border-black-300 p-4 sm:px-6">
                            <div className="flex flex-col gap-1">
                                <DialogPrimitive.Title className="text-lg leading-snug font-semibold">{t('FORM_PROMOTION.TITLE')}</DialogPrimitive.Title>
                                <DialogPrimitive.Description id="promotion-lead" className="text-sm text-black-700">
                                    {sourceTitle ? `${sourceTitle}. ` : ''}
                                    {t('FORM_PROMOTION.LEAD')}
                                </DialogPrimitive.Description>
                            </div>
                            <DialogPrimitive.Close className="-mt-1 -mr-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-md hover:bg-black-200 sm:h-9 sm:w-9">
                                <X className="h-5 w-5" aria-hidden="true" />
                                <span className="sr-only">{t('FORM_PROMOTION.CLOSE')}</span>
                            </DialogPrimitive.Close>
                        </div>

                        <div className="flex flex-col gap-4 overflow-y-auto p-4 sm:px-6" data-testid="promotion-body">
                            <div className="flex flex-col gap-1">
                                <p className="text-xs font-medium text-black-700" data-testid="promotion-step-indicator">
                                    {t('FORM_PROMOTION.STEP_OF', { current: step, total: TOTAL_STEPS })}
                                </p>
                                <h3 ref={headingRef} tabIndex={-1} className="text-base font-semibold outline-none focus-visible:underline">
                                    {step === 3 ? (applied?.created === false ? t('FORM_PROMOTION.DONE.TITLE_UPDATED') : t('FORM_PROMOTION.DONE.TITLE_NEW')) : t(`FORM_PROMOTION.${stepName}`)}
                                </h3>
                            </div>

                            {step === 1 && (
                                <WhereStep
                                    source={{ workspaceId: workspace.id, formId: form.formId }}
                                    workspaces={workspaces}
                                    loading={loading}
                                    failed={failed}
                                    targetWorkspaceId={targetWorkspaceId}
                                    onTargetWorkspace={(id) => {
                                        setTargetWorkspaceId(id);
                                        setTarget({ id: '', title: '' });
                                    }}
                                    mode={mode}
                                    onMode={(next) => {
                                        setMode(next);
                                        setTarget({ id: '', title: '' });
                                    }}
                                    targetFormId={target.id}
                                    onTargetForm={(id, title) => setTarget({ id, title })}
                                />
                            )}

                            {step === 2 && previewing.isLoading && !preview && (
                                <p role="status" className="text-sm text-black-700">
                                    {t('FORM_PROMOTION.REVIEW.LOADING')}
                                </p>
                            )}
                            {step === 2 && previewFailure && (
                                <div role="alert" data-testid={`promotion-error-${previewFailure}`} className="flex flex-col items-start gap-2 rounded border border-[#E5B9B9] bg-[#FBEFEF] p-3 text-sm">
                                    <p>{t(failureKey(previewFailure))}</p>
                                    <button type="button" className={SECONDARY} onClick={() => void review(copyPrivacy)} disabled={busy}>
                                        {t('FORM_PROMOTION.ERROR.REVIEW_AGAIN')}
                                    </button>
                                </div>
                            )}
                            {step === 2 && preview && targetWorkspace && (
                                <ReviewStep
                                    preview={preview}
                                    errors={problems}
                                    workspaceTitle={targetWorkspace.title}
                                    targetForm={mode === 'existing' && target.id ? target : null}
                                    accessUrl={accessUrl}
                                    copyPrivacy={copyPrivacy}
                                    onCopyPrivacy={changePrivacy}
                                    overwrite={overwrite}
                                    onOverwrite={setOverwrite}
                                    retentionAsk={retentionAsk}
                                    confirmRetention={confirmRetention}
                                    onConfirmRetention={setConfirmRetention}
                                    failure={applyFailure}
                                    notice={notice}
                                    onReviewAgain={() => void review(copyPrivacy)}
                                    busy={busy}
                                />
                            )}

                            {step === 3 && applied && targetWorkspace && (
                                <div className="flex flex-col gap-3 text-sm" data-testid="promotion-done">
                                    <p>{t('FORM_PROMOTION.DONE.BODY', { workspace: targetWorkspace.title })}</p>
                                    <p>{t('FORM_PROMOTION.DONE.REMINDER', { workspace: targetWorkspace.title })}</p>
                                    <Link href={dashboardFormUrl(targetWorkspace.workspaceName, applied.formId)} className={`${PRIMARY} w-fit`} data-testid="promotion-open-copy">
                                        {t('FORM_PROMOTION.DONE.OPEN')}
                                    </Link>
                                </div>
                            )}
                        </div>

                        <div className="flex flex-col-reverse gap-2 border-t border-black-300 p-4 sm:flex-row sm:justify-end sm:px-6">
                            {step === 1 && (
                                <>
                                    <DialogPrimitive.Close className={SECONDARY}>{t('FORM_PROMOTION.CANCEL')}</DialogPrimitive.Close>
                                    <button type="button" className={PRIMARY} disabled={!canContinue} onClick={goReview}>
                                        {t('FORM_PROMOTION.NEXT')}
                                    </button>
                                </>
                            )}
                            {step === 2 && (
                                <>
                                    <button type="button" className={SECONDARY} disabled={busy} onClick={() => setStep(1)}>
                                        {t('FORM_PROMOTION.BACK')}
                                    </button>
                                    <button type="button" className={PRIMARY} disabled={!ready} onClick={() => void copy()} data-testid="promotion-copy">
                                        {applying.isLoading ? t('FORM_PROMOTION.COPYING') : t('FORM_PROMOTION.COPY')}
                                    </button>
                                </>
                            )}
                            {step === 3 && <DialogPrimitive.Close className={SECONDARY}>{t('FORM_PROMOTION.CLOSE')}</DialogPrimitive.Close>}
                        </div>
                    </DialogPrimitive.Content>
                </DialogPortal>
            </DialogPrimitive.Root>
        </div>
    );
}

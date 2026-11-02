'use client';

import { ReactNode } from 'react';

import { useTranslation } from 'react-i18next';

import ChangeGroups from '@app/components/form-versions/change-groups';
import { Checkbox } from '@app/shadcn/components/ui/checkbox';
import type { PromotionPreview, PromotionProblem } from '@app/store/workspaces/form-promotion-api';

import { PromotionFailureKind, failureKey, whereOf } from './promotion-errors';

export const ROW = 'flex min-h-[44px] items-start gap-3 py-2 text-sm sm:min-h-[36px]';

/** What was adjusted, in the order the dialog says it: the count key and the sentence it is worded with. */
const ADJUSTED: Array<[string, string]> = [
    ['imagesDropped', 'IMAGES_DROPPED'],
    ['patternsDropped', 'PATTERNS_DROPPED'],
    ['listsMatchedByName', 'LISTS_MATCHED'],
    ['listsNotFound', 'LISTS_NOT_FOUND'],
    ['answerSourcesDropped', 'ANSWER_SOURCES'],
    ['shareAsChoicesOff', 'SHARE_AS_CHOICES'],
    ['libraryMarkersDropped', 'LIBRARY_MARKERS']
];

/** The automations that are counted and not copied, in the order the dialog says them. */
const NOT_COPIED: Array<[string, string]> = [
    ['webhooks', 'WEBHOOKS'],
    ['emailActions', 'EMAIL_ACTIONS'],
    ['sheets', 'SHEETS'],
    ['registrations', 'REGISTRATIONS']
];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
    return (
        <section aria-labelledby={id} className="flex flex-col gap-2">
            <h4 id={id} className="text-sm font-semibold text-black-900">
                {title}
            </h4>
            {children}
        </section>
    );
}

function Problem({ problem }: { problem: PromotionProblem }) {
    const { t } = useTranslation();
    const where = whereOf(problem.path);
    return (
        <li className="text-sm break-words">
            {where && <span className="font-medium">{where.question ? t('FORM_PROMOTION.REVIEW.WHERE_PAGE_QUESTION', { page: where.page, question: where.question }) : t('FORM_PROMOTION.REVIEW.WHERE_PAGE', { page: where.page })}: </span>}
            {problem.message}
        </li>
    );
}

export interface ReviewStepProps {
    preview: PromotionPreview;
    /** Every problem to show as an error: the preview's, or the ones the server listed when it refused the copy. */
    errors: PromotionProblem[];
    workspaceTitle: string;
    /** The target form's title and id for an existing target; none for a new form. */
    targetForm?: { id: string; title: string } | null;
    /** Where the target form's access settings are (an existing target in another workspace). */
    accessUrl?: string;
    copyPrivacy: boolean;
    onCopyPrivacy: (value: boolean) => void;
    overwrite: boolean;
    onOverwrite: (value: boolean) => void;
    /** Whether copying shortens how long the target keeps answers: a second tick is needed. */
    retentionAsk: boolean;
    confirmRetention: boolean;
    onConfirmRetention: (value: boolean) => void;
    /** The refusal of the last copy, shown as an alert with its way out. */
    failure?: PromotionFailureKind | null;
    notice?: PromotionFailureKind | null;
    onReviewAgain: () => void;
    busy: boolean;
}

/** The refusal "Restrict the target form first", with a way to that form's Access page. */
export function RestrictTargetAlert({ accessUrl, onReviewAgain, busy }: { accessUrl?: string; onReviewAgain?: () => void; busy?: boolean }) {
    const { t } = useTranslation();
    return (
        <div role="alert" data-testid="promotion-error-target_not_restricted" className="flex flex-col gap-1 rounded border border-[#E5B9B9] bg-[#FBEFEF] p-3 text-sm">
            <p className="font-semibold">{t('FORM_PROMOTION.ERROR.TARGET_NOT_RESTRICTED_TITLE')}</p>
            <p>{t('FORM_PROMOTION.ERROR.TARGET_NOT_RESTRICTED')}</p>
            {accessUrl && (
                <a href={accessUrl} target="_blank" rel="noopener noreferrer" className="flex min-h-[44px] w-fit items-center underline underline-offset-2 sm:min-h-[28px]">
                    {t('FORM_PROMOTION.ERROR.TARGET_NOT_RESTRICTED_LINK')} <span className="sr-only">{t('FORM_NAV.NEW_TAB')}</span>
                </a>
            )}
            {onReviewAgain && (
                <button type="button" onClick={onReviewAgain} disabled={busy} className="mt-1 min-h-[44px] w-fit rounded border border-black-400 bg-white px-4 text-sm font-medium hover:bg-black-200 sm:min-h-[36px]">
                    {t('FORM_PROMOTION.ERROR.REVIEW_AGAIN')}
                </button>
            )}
        </div>
    );
}

export default function ReviewStep(props: ReviewStepProps) {
    const { t } = useTranslation();
    const { preview, errors, workspaceTitle, targetForm, copyPrivacy, retentionAsk, failure, notice } = props;
    const restrictedRefusal = errors.some((e) => e.code === 'target_not_restricted') || failure === 'target_not_restricted';
    const listedErrors = errors.filter((e) => e.code !== 'target_not_restricted');
    const adjustedCounts = preview.adjusted?.counts ?? {};
    const adjusted = ADJUSTED.filter(([key]) => (adjustedCounts[key] ?? 0) > 0);
    const notCarried = preview.notCarried ? NOT_COPIED.filter(([key]) => (preview.notCarried?.[key] ?? 0) > 0) : [];
    const targetName = targetForm?.title ?? '';
    // alerts about the last attempt that the sections above already say (the problems themselves, the restriction) are not said twice
    const sayFailure = failure && failure !== 'target_not_restricted' && failure !== 'retention_confirmation_required';

    return (
        <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1 text-sm">
                <p>{targetForm ? t('FORM_PROMOTION.REVIEW.TARGET_EXISTING', { form: targetName, workspace: workspaceTitle }) : t('FORM_PROMOTION.REVIEW.TARGET_NEW', { workspace: workspaceTitle })}</p>
                <p className="text-black-700">
                    {t('FORM_PROMOTION.REVIEW.SIZE', { pages: t('FORM_PROMOTION.REVIEW.PAGES', { count: preview.counts?.pages ?? 0 }), questions: t('FORM_PROMOTION.REVIEW.QUESTIONS', { count: preview.counts?.questions ?? 0 }) })}
                </p>
                <p>{preview.copyIsRestricted ? t('FORM_PROMOTION.REVIEW.RESTRICTED') : t('FORM_PROMOTION.REVIEW.NOT_RESTRICTED')}</p>
            </div>

            {notice && (
                <p role="status" data-testid={`promotion-notice-${notice}`} className="rounded border border-black-300 bg-black-100 p-3 text-sm">
                    {t(failureKey(notice))}
                </p>
            )}

            {restrictedRefusal && <RestrictTargetAlert accessUrl={props.accessUrl} onReviewAgain={props.onReviewAgain} busy={props.busy} />}

            {listedErrors.length > 0 && (
                <div role="alert" data-testid="promotion-errors" className="flex flex-col gap-2 rounded border border-[#E5B9B9] bg-[#FBEFEF] p-3">
                    <p className="text-sm font-semibold">{t('FORM_PROMOTION.REVIEW.ERRORS_HEADING')}</p>
                    <p className="text-sm">{t('FORM_PROMOTION.REVIEW.ERRORS_INTRO')}</p>
                    <ul className="flex list-disc flex-col gap-1 pl-5">
                        {listedErrors.map((problem, index) => (
                            <Problem key={`${problem.path ?? ''}-${problem.code ?? ''}-${index}`} problem={problem} />
                        ))}
                    </ul>
                </div>
            )}

            {preview.warnings?.length > 0 && (
                <Section id="promotion-warnings" title={t('FORM_PROMOTION.REVIEW.WARNINGS_HEADING')}>
                    <ul className="flex list-disc flex-col gap-1 pl-5">
                        {preview.warnings.map((problem, index) => (
                            <Problem key={`${problem.path ?? ''}-${problem.code ?? ''}-${index}`} problem={problem} />
                        ))}
                    </ul>
                </Section>
            )}

            <Section id="promotion-changes" title={t('FORM_PROMOTION.REVIEW.CHANGES_HEADING')}>
                {preview.diff ? (
                    !preview.diff.changed && preview.diff.entries.length === 0 ? (
                        <p className="text-sm">{t('FORM_PROMOTION.REVIEW.CHANGES_NONE')}</p>
                    ) : (
                        <>
                            <ChangeGroups entries={preview.diff.entries} idPrefix="promotion-changes" heading="h5" />
                            {preview.diff.truncated && <p className="text-sm text-black-700">{t('FORM_VERSIONS.COMPARE.TRUNCATED', { count: preview.diff.entries.length })}</p>}
                        </>
                    )
                ) : (
                    <p className="text-sm">{t('FORM_PROMOTION.REVIEW.NEW_NOTE')}</p>
                )}
            </Section>

            <Section id="promotion-not-copied" title={t('FORM_PROMOTION.REVIEW.NOT_COPIED_HEADING')}>
                <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
                    <li>{t('FORM_PROMOTION.REVIEW.NOT_COPIED_ANSWERS')}</li>
                    {notCarried.length > 0 && <li>{t('FORM_PROMOTION.REVIEW.NOT_COPIED_COUNTS', { list: notCarried.map(([key, label]) => t(`FORM_PROMOTION.REVIEW.${label}`, { count: preview.notCarried?.[key] ?? 0 })).join(', ') })}</li>}
                    <li>{t('FORM_PROMOTION.REVIEW.NOT_COPIED_ALSO')}</li>
                </ul>
            </Section>

            {adjusted.length > 0 && (
                <Section id="promotion-adjusted" title={t('FORM_PROMOTION.REVIEW.ADJUSTED_HEADING')}>
                    <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
                        {adjusted.map(([key, label]) => (
                            <li key={key}>{t(`FORM_PROMOTION.REVIEW.${label}`, { count: adjustedCounts[key] })}</li>
                        ))}
                    </ul>
                </Section>
            )}

            {targetForm && (
                <Section id="promotion-privacy" title={t('FORM_PROMOTION.REVIEW.PRIVACY_HEADING')}>
                    <label htmlFor="promotion-copy-privacy" className={`${ROW} cursor-pointer items-center`}>
                        <Checkbox id="promotion-copy-privacy" checked={copyPrivacy} disabled={props.busy} onCheckedChange={(value: boolean | 'indeterminate') => props.onCopyPrivacy(value === true)} className="shrink-0" />
                        <span>{t('FORM_PROMOTION.REVIEW.COPY_PRIVACY')}</span>
                    </label>
                    <p className="text-sm text-black-700">{copyPrivacy ? t('FORM_PROMOTION.REVIEW.REPLACES', { form: targetName }) : t('FORM_PROMOTION.REVIEW.KEEPS')}</p>
                    {copyPrivacy && retentionAsk && (
                        <div className="flex flex-col gap-1 rounded border border-[#E5B9B9] bg-[#FBEFEF] p-3">
                            <p role="alert" data-testid="promotion-retention-warning" className="text-sm font-medium">
                                {t('FORM_PROMOTION.REVIEW.RETENTION_WARNING', { form: targetName })}
                            </p>
                            <label htmlFor="promotion-confirm-retention" className={`${ROW} cursor-pointer items-center`}>
                                <Checkbox id="promotion-confirm-retention" checked={props.confirmRetention} disabled={props.busy} onCheckedChange={(value: boolean | 'indeterminate') => props.onConfirmRetention(value === true)} className="shrink-0" />
                                <span>{t('FORM_PROMOTION.REVIEW.RETENTION_CONFIRM')}</span>
                            </label>
                        </div>
                    )}
                </Section>
            )}

            {targetForm && preview.targetChangedSinceLastPromotion && (
                <div className="flex flex-col gap-1 rounded border border-black-300 bg-black-100 p-3">
                    <p className="text-sm">{t('FORM_PROMOTION.REVIEW.TARGET_CHANGED')}</p>
                    <label htmlFor="promotion-overwrite" className={`${ROW} cursor-pointer items-center`}>
                        <Checkbox id="promotion-overwrite" checked={props.overwrite} disabled={props.busy} onCheckedChange={(value: boolean | 'indeterminate') => props.onOverwrite(value === true)} className="shrink-0" />
                        <span>{t('FORM_PROMOTION.REVIEW.OVERWRITE')}</span>
                    </label>
                </div>
            )}

            <p className="text-xs text-black-700">{t('FORM_PROMOTION.REVIEW.TEXTS_NOTE')}</p>

            {sayFailure && (
                <div role="alert" data-testid={`promotion-error-${failure}`} className="flex flex-col items-start gap-2 rounded border border-[#E5B9B9] bg-[#FBEFEF] p-3 text-sm">
                    <p>{t(failureKey(failure))}</p>
                    {(failure === 'target_changed' || failure === 'idempotency_in_progress' || failure === 'unknown') && (
                        <button type="button" onClick={props.onReviewAgain} disabled={props.busy} className="min-h-[44px] rounded border border-black-400 bg-white px-4 text-sm font-medium hover:bg-black-200 sm:min-h-[36px]">
                            {t('FORM_PROMOTION.ERROR.REVIEW_AGAIN')}
                        </button>
                    )}
                </div>
            )}
            {failure === 'retention_confirmation_required' && (
                <p role="alert" data-testid="promotion-error-retention_confirmation_required" className="rounded border border-[#E5B9B9] bg-[#FBEFEF] p-3 text-sm">
                    {t(failureKey('retention_confirmation_required'))}
                </p>
            )}
        </div>
    );
}

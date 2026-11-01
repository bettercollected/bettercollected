'use client';

import { useState } from 'react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import useFormAtom from '@app/store/jotai/form-file';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState, useVisitedSlides } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { useRespondentDraft } from '@app/store/jotai/respondent-draft';
import { useSendFlowEventMutation, useSubmitResponseMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { aiNoticeTokenToSend } from '@app/utils/ai-notice';
import { localToday } from '@app/utils/calculated-fields';
import { getFlowSessionId } from '@app/utils/flow-session';
import { normalizeGroupAnswersForSubmit, parseScopedFieldId } from '@app/utils/repeating-groups';
import { REVIEW_SLIDE, pathPages } from '@app/utils/review-page';
import { focusQuestionInGroup, scrollToDivById } from '@app/utils/scroll-utils';
import { firstPageWithError, formRefusal, historyBackTo, serverAnswerErrors, serverInvalidations } from '@app/utils/server-answer-errors';

/** The message for a submission the server refused because the form takes no responses. */
export const SUBMIT_REFUSED = { closed: 'NAV.SUBMIT_CLOSED', not_yet_open: 'NAV.SUBMIT_NOT_OPEN', full: 'NAV.SUBMIT_FULL' } as const;

/** Does this submission carry the drawing of a signature question? */
export function sendsDrawnSignature(slides: StandardFormFieldDto[] | undefined, files: ReadonlyArray<{ fieldId: string }>): boolean {
    const signatureIds = new Set((slides ?? []).flatMap((slide) => slide?.properties?.fields ?? []).filter((field) => field.type === FieldTypes.SIGNATURE).map((field) => field.id));
    return files.some((file) => signatureIds.has(file.fieldId));
}

/** `unmapped`: the server refused some answers (422) that belong to no page the respondent can go to; `signature_unavailable`: it could not process a drawn signature just now (503). */
export type SubmitError = false | 'failed' | 'unmapped' | 'closed' | 'not_yet_open' | 'full' | 'signature_unavailable';

/** The message to keep by the button for a failed submission. */
export const submitErrorKey = (error: Exclude<SubmitError, false>) => (error === 'failed' ? 'NAV.SUBMIT_ERROR' : error === 'unmapped' ? 'NAV.SUBMIT_UNMAPPED' : error === 'signature_unavailable' ? 'SIGNATURE.SUBMIT_UNAVAILABLE' : SUBMIT_REFUSED[error]);

/**
 * Anonymous drop-off breadcrumb: page to page, never answers, never in preview.
 */
export function useEmitFlow(isPreviewMode: boolean) {
    const standardForm = useAppSelector(selectResponderForm);
    const workspace = useAppSelector(selectWorkspace);
    const [sendFlowEvent] = useSendFlowEventMutation();
    return (fromPage: string, toPage: string) => {
        if (isPreviewMode || !workspace?.id || !standardForm?.formId) return;
        sendFlowEvent({ workspaceId: workspace.id, formId: standardForm.formId, sessionId: getFlowSessionId(standardForm.formId), fromPage, toPage }).catch(() => {});
    };
}

/**
 * Sending the form, from the last page or from the review page: the body the
 * server gets (answers as `normalizeGroupAnswersForSubmit` reads them over the
 * pages the respondent went through, hidden-field values, files, the identity
 * choice), the ending to show afterwards, and what to do when the server says
 * no. A form that stopped taking responses while it was filled in (closed,
 * not open, full: 409) keeps the answers and says so by the button; answers it
 * refused (422) are put on their questions, and the respondent goes back to
 * the first page that has one. Nothing is sent before this runs.
 */
export function useFinishForm(isPreviewMode: boolean) {
    const { toast } = useToast();
    const { t } = useRespondentLanguage();
    const standardForm = useAppSelector(selectResponderForm);
    const { currentSlide, setCurrentSlideToThankyouPage, setResponderState, responderState } = useResponderState();
    const { formResponse, setInvalidFields, setFormResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    const visited = useVisitedSlides();
    const workspace = useAppSelector(selectWorkspace);
    const [submitResponse, { isLoading }] = useSubmitResponseMutation();
    const { files } = useFormAtom();
    const authState = useAppSelector(selectAuth);
    // The key of the anonymous draft this browser holds, if any: the submit deletes that draft.
    const { draft: savedDraft } = useRespondentDraft(standardForm?.formId);
    // A failed submission, shown by the button until the next attempt.
    const [submitError, setSubmitError] = useState<SubmitError>(false);

    // Identity sharing is opt-in (DESIGN.md §5 — "leave consent unchecked;
    // the person opts in"): until the responder touches the checkbox, a logged-in
    // responder on an identity-optional form stays anonymous. Forms that require
    // a verified identity keep it attached, as they state up front.
    const identityOptional = !!authState.id && !standardForm?.settings?.requireVerifiedIdentity;
    const effectiveAnonymize = formResponse.anonymize ?? identityOptional;

    const submitFormResponse = async () => {
        const formData = new FormData();

        const postBody = {
            form_id: standardForm?.formId,
            // Repeating groups the responder saw carry at least their minimum items.
            // ...and groups hidden by logic or off the visited path are dropped.
            answers: normalizeGroupAnswersForSubmit(standardForm?.fields, formResponse.answers ?? {}, visited),
            // Hidden-field (URL parameter) values captured when the form loaded.
            ...(Object.keys(hiddenValues).length ? { hidden_fields: hiddenValues } : {}),
            anonymize: effectiveAnonymize,
            form_version: standardForm?.version || 1
        };

        formData.append('response', JSON.stringify(postBody));
        // The date calculations used (today()); the server takes it when it is plausible.
        formData.append('today', localToday());
        const aiNoticeToken = aiNoticeTokenToSend(standardForm);
        if (aiNoticeToken) formData.append('ai_notice_token', aiNoticeToken);
        if (savedDraft.editKey) formData.append('draft_key', savedDraft.editKey);
        files.forEach((fileObj) => {
            formData.append('files', fileObj.file, fileObj.fileName);
            formData.append('file_field_ids', fileObj.fieldId);
            formData.append('file_ids', fileObj.fileId);
        });
        const response: any = await submitResponse({
            workspaceId: workspace.id,
            formId: standardForm?.formId,
            body: formData
        });
        if (!response.data) {
            const failure: Error & { response?: unknown } = new Error('The response was not accepted.');
            failure.response = response?.error;
            throw failure;
        }
        // Reflect what was actually submitted, so the thank-you page reports
        // the anonymity state truthfully.
        if (formResponse.anonymize === undefined) {
            setFormResponse({ ...formResponse, anonymize: effectiveAnonymize });
        }
        return response.data;
    };

    // The server refused some answers (422 invalid_answers): put its problems
    // on the questions and go back to the first page that has one.
    const showServerAnswerErrors = (error: unknown): boolean => {
        const errors = serverAnswerErrors(error);
        if (!errors) return false;
        const slides = standardForm?.fields ?? [];
        const invalid = serverInvalidations(slides, errors);
        setInvalidFields(invalid);
        toast({ description: t('NAV.SUBMIT_INVALID'), variant: 'destructive' });
        const page = firstPageWithError(slides, errors);
        // Nothing to go to: the toast alone is gone in a moment, so the message stays by the button
        if (page < 0) setSubmitError('unmapped');
        if (page >= 0 && page !== currentSlide) {
            const fromReview = currentSlide === REVIEW_SLIDE;
            setResponderState({
                ...responderState,
                currentSlide: page,
                currentField: 0,
                prevActiveField: -1,
                prevActiveSlide: currentSlide,
                // The review is not a page of the path; from it, "Back to review" stays on offer
                history: pathPages(historyBackTo(responderState.history, currentSlide, page)),
                reviewPath: fromReview ? pathPages(responderState.history) : responderState.reviewPath
            });
        }
        const firstKey = Object.keys(invalid)[0];
        // after the page change has rendered; as onNext does
        if (firstKey)
            setTimeout(() => {
                if (parseScopedFieldId(firstKey)) focusQuestionInGroup(firstKey);
                else scrollToDivById(firstKey, undefined, { focusControl: true });
            }, 600);
        return true;
    };

    // Submit, then show the ending the deciding jump named (`endingId`), or
    // the default ending. Respondents never see an ending without submitting.
    const finishForm = (endingId?: string) => {
        if (isPreviewMode) setCurrentSlideToThankyouPage(endingId);
        else
            submitFormResponse()
                .then((responderId) => {
                    setResponderState({
                        ...responderState,
                        currentSlide: -2,
                        responderId,
                        endingId,
                        reviewPath: undefined
                    });
                })
                .catch((e) => {
                    // The form stopped taking responses while it was being filled
                    // in (closed, not open, full): say so, and keep the answers
                    // (nothing was stored).
                    const refusal = formRefusal(e?.response);
                    if (refusal) {
                        toast({ description: t(SUBMIT_REFUSED[refusal]), variant: 'destructive' });
                        setSubmitError(refusal);
                    } else if ((e?.response?.status === 503 || e?.response?.status === 429) && sendsDrawnSignature(standardForm?.fields, files)) {
                        // the server could not process the drawn image just now (unavailable, busy, or too many drawn signatures
                        // from here in the last minute): nothing was stored, the drawing is kept, typing works
                        toast({ description: t('SIGNATURE.SUBMIT_UNAVAILABLE'), variant: 'destructive' });
                        setSubmitError('signature_unavailable');
                    } else if (!showServerAnswerErrors(e?.response)) {
                        toast({ description: t('NAV.SUBMIT_ERROR'), variant: 'destructive' });
                        setSubmitError('failed');
                    }
                });
    };

    return { finishForm, isLoading, submitError, setSubmitError, effectiveAnonymize };
}

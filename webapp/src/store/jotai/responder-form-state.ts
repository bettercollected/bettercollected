import { useMemo } from 'react';

import { atom, useAtom, useAtomValue } from 'jotai';

import { shownSlide } from '@app/utils/closed-form';
import { REVIEW_SLIDE, pathPages } from '@app/utils/review-page';

import { selectResponderForm } from '../forms/slice';
import { useAppSelector } from '../hooks';

export interface ResponderFormState {
    currentSlide: number;
    prevActiveField: number;
    currentField: number;
    prevActiveSlide: number;
    responderId?: string;
    /**
     * The ending the deciding page jump named (utils/endings.ts); unset: the
     * default ending. Set when the form is submitted.
     */
    endingId?: string;
    // Slides actually visited, in order — lets Back retrace jumps instead of
    // assuming a linear -1. Pushed on every forward move, popped on Back.
    history: number[];
    /**
     * Set while the respondent edits a page from the review page
     * (utils/review-page.ts): the pages they had reviewed, in order. "Back to
     * review" is offered on a page of it, and its pages still count as
     * visited, so rules and submission read the same path meanwhile.
     */
    reviewPath?: number[];
    /** The ending the deciding page jump named, kept for the submit on the review page. */
    reviewEndingId?: string;
}

const initialresponderState: ResponderFormState = {
    prevActiveField: -1,
    prevActiveSlide: -1,
    currentField: 0,
    currentSlide: -1,
    history: []
};

const responderFormStateAtom = atom<ResponderFormState>(initialresponderState);

export const useResponderState = () => {
    const [responderState, setResponderState] = useAtom(responderFormStateAtom);

    const standardForm = useAppSelector(selectResponderForm);

    // After the page transition (500 ms) the page left is forgotten: only when
    // the respondent is still on the page they moved to, never over a newer move.
    const settle = (slide: number) =>
        setTimeout(() => {
            setResponderState((previous) => (previous.currentSlide === slide ? { ...previous, prevActiveSlide: slide } : previous));
        }, 500);

    // Move to an arbitrary slide (linear next or a page-jump target), recording the
    // slide we came from so Back can retrace it.
    const goToSlide = (targetSlideNumber: number) => {
        setResponderState((previous) => {
            const from = previous.currentSlide;
            return {
                ...previous,
                currentSlide: targetSlideNumber,
                currentField: 0,
                prevActiveField: -1,
                prevActiveSlide: from,
                history: [...(previous.history || []), from],
                // Leaving the pages that were reviewed: nothing to go back to
                reviewPath: previous.reviewPath?.includes(targetSlideNumber) ? previous.reviewPath : undefined
            };
        });
        settle(targetSlideNumber);
    };

    const nextSlide = () => goToSlide(responderState.currentSlide + 1);

    const previousSlide = () => {
        const history = [...(responderState.history || [])];
        const from = responderState.currentSlide;
        const previousSlideNumber = history.length ? (history.pop() as number) : responderState.currentSlide - 1;
        setResponderState((previous) => ({
            ...previous,
            currentSlide: previousSlideNumber,
            currentField: 0,
            prevActiveField: -1,
            prevActiveSlide: from,
            history
        }));
        settle(previousSlideNumber);
    };

    /**
     * To the review page, after the last page (or a jump that submits): the
     * pages gone through become the path it lists; `endingId` is the ending
     * the deciding jump named.
     */
    const goToReview = (endingId?: string) => {
        setResponderState((previous) => ({
            ...previous,
            currentSlide: REVIEW_SLIDE,
            currentField: 0,
            prevActiveField: -1,
            prevActiveSlide: previous.currentSlide,
            history: pathPages([...(previous.history || []), previous.currentSlide]),
            reviewPath: undefined,
            reviewEndingId: endingId
        }));
        settle(REVIEW_SLIDE);
    };

    /** "Edit" on the review page: to that page, with the way back to the review kept. */
    const editFromReview = (slideIndex: number) => {
        setResponderState((previous) => {
            const path = pathPages(previous.history);
            const at = path.indexOf(slideIndex);
            if (at < 0) return previous;
            return { ...previous, currentSlide: slideIndex, currentField: 0, prevActiveField: -1, prevActiveSlide: previous.currentSlide, history: path.slice(0, at), reviewPath: path };
        });
        settle(slideIndex);
    };

    /** "Back to review": the review again, over `path` (the pages as they stand after the edit). */
    const returnToReview = (path: number[], endingId?: string) => {
        setResponderState((previous) => ({
            ...previous,
            currentSlide: REVIEW_SLIDE,
            currentField: 0,
            prevActiveField: -1,
            prevActiveSlide: previous.currentSlide,
            history: pathPages(path),
            reviewPath: undefined,
            reviewEndingId: endingId
        }));
        settle(REVIEW_SLIDE);
    };

    /** On with the form from `slide`, as if the pages of `path` had just been gone through (an edit changed where the form goes). */
    const continueFrom = (path: number[], slide: number) => {
        setResponderState((previous) => ({ ...previous, currentSlide: slide, currentField: 0, prevActiveField: -1, prevActiveSlide: previous.currentSlide, history: pathPages(path), reviewPath: undefined }));
        settle(slide);
    };

    const setCurrentSlideToThankyouPage = (endingId?: string) => {
        setResponderState({
            ...responderState,
            currentSlide: -2,
            endingId
        });
    };

    const setCurrentSlideToWelcomePage = () => {
        setResponderState({
            ...responderState,
            currentSlide: -1,
            history: [],
            reviewPath: undefined,
            reviewEndingId: undefined
        });
    };

    const setCurrentField = (currentField: number) => {
        setResponderState({
            ...responderState,
            currentField: currentField,
            prevActiveField: responderState.currentField
        });
    };

    const nextField = () => {
        if (standardForm?.fields?.[responderState.currentSlide]?.properties?.fields?.length !== responderState.currentField + 1)
            setResponderState({
                ...responderState,
                currentField: responderState.currentField + 1,
                prevActiveField: responderState.currentField
            });
    };

    const resetResponderState = () => {
        setResponderState(initialresponderState);
    };

    return {
        responderState,
        currentSlide: responderState.currentSlide,
        currentField: responderState.currentField,
        prevActiveField: responderState.prevActiveField,
        prevActiveSlide: responderState.prevActiveSlide,
        responderId: responderState.responderId,
        endingId: responderState.endingId,
        resetResponderState,
        nextSlide,
        goToSlide,
        setCurrentField,
        previousSlide,
        nextField,
        setCurrentSlideToThankyouPage,
        setResponderState,
        setCurrentSlideToWelcomePage,
        goToReview,
        editFromReview,
        returnToReview,
        continueFrom
    };
};

/**
 * The pages the respondent has been through, with the one they are on: the
 * path a submission is read along (utils/repeating-groups.ts
 * `normalizeGroupAnswersForSubmit`), and so what field rules are decided from.
 */
export const useVisitedSlides = (): number[] => {
    const { history, currentSlide, reviewPath } = useAtomValue(responderFormStateAtom);
    return useMemo(() => [...(history || []), currentSlide, ...(reviewPath || [])], [history, currentSlide, reviewPath]);
};

/**
 * The page on screen for the respondent's place (utils/closed-form.ts): the
 * welcome page while the form is closed, unless they are on an ending. The
 * form and the trust strip below it read this, so they always agree.
 */
export const useShownSlide = () => {
    const { currentSlide } = useAtomValue(responderFormStateAtom);
    const standardForm = useAppSelector(selectResponderForm);
    return shownSlide(standardForm, currentSlide);
};

import { atom, useAtom } from 'jotai';

import { selectForm } from '../forms/slice';
import { useAppSelector } from '../hooks';

export interface ResponderFormState {
    currentSlide: number;
    prevActiveField: number;
    currentField: number;
    prevActiveSlide: number;
    responderId?: string;
    // Slides actually visited, in order — lets Back retrace jumps instead of
    // assuming a linear -1. Pushed on every forward move, popped on Back.
    history: number[];
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

    const standardForm = useAppSelector(selectForm);

    // Move to an arbitrary slide (linear next or a page-jump target), recording the
    // slide we came from so Back can retrace it.
    const goToSlide = (targetSlideNumber: number) => {
        const from = responderState.currentSlide;
        const history = [...(responderState.history || []), from];
        setResponderState({
            ...responderState,
            currentSlide: targetSlideNumber,
            currentField: 0,
            prevActiveField: -1,
            prevActiveSlide: from,
            history
        });
        setTimeout(() => {
            setResponderState({
                ...responderState,
                currentSlide: targetSlideNumber,
                currentField: 0,
                prevActiveField: -1,
                prevActiveSlide: targetSlideNumber,
                history
            });
        }, 500);
    };

    const nextSlide = () => goToSlide(responderState.currentSlide + 1);

    const previousSlide = () => {
        const history = [...(responderState.history || [])];
        const from = responderState.currentSlide;
        const previousSlideNumber = history.length ? (history.pop() as number) : responderState.currentSlide - 1;
        setResponderState({
            ...responderState,
            currentSlide: previousSlideNumber,
            currentField: 0,
            prevActiveField: -1,
            prevActiveSlide: from,
            history
        });
        setTimeout(() => {
            setResponderState({
                ...responderState,
                currentSlide: previousSlideNumber,
                currentField: 0,
                prevActiveField: -1,
                prevActiveSlide: previousSlideNumber,
                history
            });
        }, 500);
    };

    const setCurrentSlideToThankyouPage = () => {
        setResponderState({
            ...responderState,
            currentSlide: -2
        });
    };

    const setCurrentSlideToWelcomePage = () => {
        setResponderState({
            ...responderState,
            currentSlide: -1,
            history: []
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
        resetResponderState,
        nextSlide,
        goToSlide,
        setCurrentField,
        previousSlide,
        nextField,
        setCurrentSlideToThankyouPage,
        setResponderState,
        setCurrentSlideToWelcomePage
    };
};

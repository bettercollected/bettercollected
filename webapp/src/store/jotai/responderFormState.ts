import { atom, useAtom } from 'jotai';

import { selectForm } from '../forms/slice';
import { useAppSelector } from '../hooks';

export interface ResponderFormState {
    currentSlide: number;
    prevActiveField: number;
    currentField: number;
    prevActiveSlide: number;
}

const initialresponderState: ResponderFormState = {
    prevActiveField: -1,
    prevActiveSlide: -1,
    currentField: 0,
    currentSlide: -1
};

const responderFormStateAtom = atom<ResponderFormState>(initialresponderState);

export const useResponderState = () => {
    const [responderState, setResponderState] = useAtom(responderFormStateAtom);

    const standardForm = useAppSelector(selectForm);

    const nextSlide = () => {
        const nextSlideNumber = responderState.currentSlide + 1;
        setResponderState({
            ...responderState,
            currentSlide: nextSlideNumber,
            currentField: 0,
            prevActiveField: -1,
            prevActiveSlide: responderState.currentSlide
        });

        setTimeout(() => {
            setResponderState({
                ...responderState,
                currentSlide: nextSlideNumber,
                currentField: 0,
                prevActiveField: -1,
                prevActiveSlide: responderState.currentSlide + 1
            });
        }, 500);
    };

    const previousSlide = () => {
        const previousSlideNumber = responderState.currentSlide - 1;
        setResponderState({
            ...responderState,
            currentSlide: previousSlideNumber,
            currentField: 0,
            prevActiveField: -1,
            prevActiveSlide: responderState.currentSlide
        });
        setTimeout(() => {
            setResponderState({
                ...responderState,
                currentSlide: previousSlideNumber,
                currentField: 0,
                prevActiveField: -1,
                prevActiveSlide: responderState.currentSlide - 1
            });
        }, 500);
    };

    const setCurrentSlideToThankyouPage = () => {
        setResponderState({
            ...responderState,
            currentSlide: -2
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
        resetResponderState,
        nextSlide,
        setCurrentField,
        previousSlide,
        nextField,
        setCurrentSlideToThankyouPage
    };
};

import { atom, useAtom } from 'jotai';

import { useStandardForm } from './fetchedForm';

export interface ResponderFormState {
    currentSlide: number;
    prevActiveField: number;
    currentField: number;
}

const initialresponderState: ResponderFormState = {
    prevActiveField: -1,
    currentField: 0,
    currentSlide: -1
};

const responderFormStateAtom = atom<ResponderFormState>(initialresponderState);

export const useResponderState = () => {
    const [responderState, setResponderState] = useAtom(responderFormStateAtom);

    const { standardForm } = useStandardForm();

    const nextSlide = () => {
        const nextSlideNumber = responderState.currentSlide + 1;
        setResponderState({
            ...responderState,
            currentSlide: nextSlideNumber,
            currentField: 0,
            prevActiveField: -1
        });
    };

    const previousSlide = () => {
        setResponderState({
            ...responderState,
            currentSlide: responderState.currentSlide - 1
        });
        setCurrentField(0);
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
        if (
            standardForm?.fields?.[responderState.currentSlide]?.properties?.fields
                ?.length !==
            responderState.currentField + 1
        )
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
        resetResponderState,
        nextSlide,
        setCurrentField,
        previousSlide,
        nextField,
        setCurrentSlideToThankyouPage
    };
};

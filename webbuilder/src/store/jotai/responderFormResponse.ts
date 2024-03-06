import { set } from 'lodash';

import { atom, useAtom } from 'jotai';

interface FormResponse {
    currentSlide: number;
    formId: string;
    answers?: {
        [fieldId: string]: {
            type: string;
            text?: string;
            number?: number;
            email?: string;
            date?: string;
            phoneNumber?: string;
            url?: string;
        };
    };
    consent?: Array<any>;
}

const initialFormResponse: FormResponse = {
    formId: '',
    currentSlide: -1
};

const formResponseAtom = atom<FormResponse>(initialFormResponse);

export const useFormResponse = () => {
    const [formResponse, setFormResponse] = useAtom(formResponseAtom);

    const nextSlide = () => {
        const nextSlideNumber = formResponse.currentSlide + 1;
        setFormResponse({
            ...formResponse,
            currentSlide: nextSlideNumber
        });
    };

    const previousSlide = () => {
        setFormResponse({
            ...formResponse,
            currentSlide: formResponse.currentSlide + 1
        });
    };

    const setCurrentSlideToThankyouPage = () => {
        setFormResponse({
            ...formResponse,
            currentSlide: -2
        });
    };
    return {
        formResponse,
        currentSlide: formResponse.currentSlide,
        nextSlide,
        previousSlide,
        setFormResponse,
        setCurrentSlideToThankyouPage
    };
};

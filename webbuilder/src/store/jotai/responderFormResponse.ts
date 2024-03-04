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
    currentSlide: -1,
};

const formResponseAtom = atom<FormResponse>(initialFormResponse);

export const useFormResponse = () => {
    const [formResponse, setFormResponse] = useAtom(formResponseAtom);

    const nextSlide = () => {
        setFormResponse({
            ...formResponse,
            currentSlide: formResponse.currentSlide + 1
        });
    };

    const previousSlide = () => {
        setFormResponse({
            ...formResponse,
            currentSlide: formResponse.currentSlide + 1
        });
    };
    return {
        formResponse,
        nextSlide,
        previousSlide,
        setFormResponse
    };
};

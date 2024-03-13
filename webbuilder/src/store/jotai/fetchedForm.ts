import { atom, useAtom } from 'jotai';

import { FormField } from '@app/models/dtos/form';

export default interface StandardForm {
    formId: string;
    title: string;
    description?: string;
    fields?: Array<FormField>;
    thankYouMessage?: string;
    thankYouButtonText?: string;
    buttonText?: string;
    buttonLink?: string;
    theme?: {
        title: string;
        primary: string;
        secondary: string;
        tertiary: string;
        accent: string;
    };
    settings?: {
        pinned?: boolean;
        customUrl?: string;
        private?: boolean;
        hidden?: boolean;
        requireVerifiedIdentity?: boolean;
        disableBrnding?: boolean;
    };
}

const fetchedFormAtom = atom<StandardForm>({
    formId: '',
    title: '',
    description: ''
});

export const useStandardForm = () => {
    const [standardForm, setStandardForm] = useAtom(fetchedFormAtom);

    return { standardForm, setStandardForm };
};

export const useFormSlide = (slideIndex: number) => {
    const [standardForm] = useAtom(fetchedFormAtom);
    const getFormSlide = () => {
        if (
            !standardForm.fields ||
            !standardForm?.fields?.length ||
            slideIndex > standardForm?.fields?.length
        ) {
            return;
        }
        return standardForm.fields[slideIndex];
    };

    return getFormSlide();
};

export const useFormTheme = () => {
    const [{ theme }] = useAtom(fetchedFormAtom);

    return theme;
};

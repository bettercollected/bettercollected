import { atom, useAtom } from 'jotai';

import { StandardFormDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';

const fetchedFormAtom = atom<StandardFormDto>({
    formId: '',
    title: '',
    description: '',
    welcomePage: {
        title: '',
        layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
    },
    thankyouPage: [
        {
            layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
        }
    ],
    fields: [],
    theme: {
        title: '',
        primary: '',
        secondary: '',
        tertiary: '',
        accent: ''
    }
});

export const useStandardForm = () => {
    const [standardForm, setStandardForm] = useAtom(fetchedFormAtom);

    return { standardForm, setStandardForm };
};

export const useFormSlide = (slideIndex: number) => {
    const [standardForm] = useAtom(fetchedFormAtom);
    const getFormSlide = () => {
        if (!standardForm.fields || !standardForm?.fields?.length || slideIndex > standardForm?.fields?.length) {
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

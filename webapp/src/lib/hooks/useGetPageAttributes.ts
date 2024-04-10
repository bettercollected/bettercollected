'use client';

import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

const useGetPageAttributes = (pageIndex: number, thankyouPageIndex: number = 0) => {
    const { formState } = useFormState();
    const { formFields } = useFormFieldsAtom();
    if (pageIndex === -10) {
        const layout = formState?.welcomePage?.layout;
        const imageUrl = formState?.welcomePage?.imageUrl;
        return { layout, imageUrl };
    } else if (pageIndex === -20) {
        const layout = formState?.thankyouPage?.[thankyouPageIndex]?.layout;
        const imageUrl = formState?.thankyouPage?.[thankyouPageIndex]?.imageUrl;
        return { layout, imageUrl };
    } else {
        const layout = formFields[pageIndex]?.properties?.layout;
        const imageUrl = formFields[pageIndex]?.imageUrl;
        return { layout, imageUrl };
    }
};

export default useGetPageAttributes;

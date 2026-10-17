'use client';

import { useDocValue } from '@app/store/jotai/entity-hooks';
import { useFormState } from '@app/store/jotai/form';

const useGetPageAttributes = (pageIndex: number, thankyouPageIndex: number = 0) => {
    const { formState } = useFormState();
    // The page's layout and image only: editing a question does not re-render the caller.
    const pageLayout = useDocValue((doc) => doc.fields?.[pageIndex]?.properties?.layout, [pageIndex]);
    const pageImageUrl = useDocValue((doc) => doc.fields?.[pageIndex]?.imageUrl, [pageIndex]);
    if (pageIndex === -10) {
        const layout = formState?.welcomePage?.layout;
        const imageUrl = formState?.welcomePage?.imageUrl;
        return { layout, imageUrl };
    } else if (pageIndex === -20) {
        const layout = formState?.thankyouPage?.[thankyouPageIndex]?.layout;
        const imageUrl = formState?.thankyouPage?.[thankyouPageIndex]?.imageUrl;
        return { layout, imageUrl };
    } else {
        return { layout: pageLayout, imageUrl: pageImageUrl };
    }
};

export default useGetPageAttributes;

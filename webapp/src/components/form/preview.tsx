import React from 'react';

import { FormTabContent } from '@app/components/dashboard/form-tab-content';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';

export default function FormPreview() {
    const form = useAppSelector(selectForm);
    return (
        <div className="flex lg:flex-row flex-col-reverse gap-10  w-full   ">
            <FormTabContent form={form} />
        </div>
    );
}

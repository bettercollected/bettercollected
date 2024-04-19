import React from 'react';

import FormRenderer from '../form/renderer/form-renderer';
import { StandardFormDto } from '@app/models/dtos/form';

export const FormTabContent = ({ form }: { form: StandardFormDto }) => {
    console.log(form);
    if (form?.builderVersion === 'v2') {
        return null;
    }
    return (
        <div className="flex w-full items-center rounded bg-white ">
            <FormRenderer form={form} enabled={false} isDisabled={true} />
        </div>
    );
};

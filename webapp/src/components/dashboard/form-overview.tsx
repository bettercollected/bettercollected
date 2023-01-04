import React from 'react';

import FormRenderer from '../form/renderer/form-renderer';

export const FormTabContent = ({ form }: any) => {
    return (
        <div className="w-full">
            <FormRenderer form={form} />
        </div>
    );
};

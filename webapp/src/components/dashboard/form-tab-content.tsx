import React from 'react';

import FormRenderer from '../form/renderer/form-renderer';

export const FormTabContent = ({ form }: any) => {
    return (
        <div className="w-full rounded bg-white flex items-center ">
            <FormRenderer form={form} enabled={false} isDisabled={true} />
        </div>
    );
};
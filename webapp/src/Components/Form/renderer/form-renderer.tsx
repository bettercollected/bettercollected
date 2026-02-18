'use client';

import React from 'react';
import {IndividualFormResponse} from "@app/Components/modal-views/full-screen-modals/view-response-full-modal-view";
import {getFieldsFromV2Form} from '@app/utils/formUtils';

interface FormRendererProps {
    form: any;
    response?: any;
    enabled?: boolean;
    isDisabled?: boolean;
}

FormRenderer.defaultProps = {
    enabled: false
};

export default function FormRenderer({ form, response }: FormRendererProps) {
    if (form?.builderVersion === 'v2') {
        return (
            <div data-testid="form-renderer" className="relative flex w-full justify-center md:px-0">
                <div className="h-full w-full bg-white px-5 md:px-10 lg:px-28">
                    <IndividualFormResponse 
                        response={response} 
                        formFields={getFieldsFromV2Form(form) || []} 
                        form={form}
                    />
                </div>
            </div>
        );
    }

    return null;
}

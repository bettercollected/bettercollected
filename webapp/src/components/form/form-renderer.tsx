'use client';

import { IndividualFormResponse } from "@app/components/modal-views/full-screen-modals/view-response-full-modal-view";
import { isShownToRespondents } from '@app/utils/calculated-fields';
import { getFieldsFromV2Form } from '@app/utils/form-utils';

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
                <div className="h-full w-full bg-white">
                    <IndividualFormResponse
                        response={response}
                        // the respondent's own copy: no calculation kept from them
                        formFields={(getFieldsFromV2Form(form) || []).filter(isShownToRespondents)}
                        form={form}
                    />
                </div>
            </div>
        );
    }

    return null;
}

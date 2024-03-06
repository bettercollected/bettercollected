'use client';

import { useEffect, useState } from 'react';

import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import FormSlide from '@app/views/organism/Form/FormSlide';
import WelcomeSlide from '@app/views/organism/Form/WelcomeSlide';

export default function FormPage({
    params
}: {
    params: { formId: string; workspaceName: string };
}) {
    const { formResponse } = useFormResponse();
    const { formId } = params;
    const { setStandardForm } = useStandardForm();

    useEffect(() => {
        const forms = JSON.parse(localStorage.getItem('forms') || '{}');
        const currentForm = forms[formId];
        if (currentForm) {
            setStandardForm(currentForm);
        }
    }, []);

    return (
        <div className="h-screen w-screen">
            {formResponse?.currentSlide === -1 && <WelcomeSlide />}
            {formResponse?.currentSlide === -2 && <div>This will be End Slide</div>}
            {formResponse?.currentSlide >= 0 && (
                <FormSlide index={formResponse.currentSlide} />
            )}
        </div>
    );
}

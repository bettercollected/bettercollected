'use client';

import { useEffect, useState } from 'react';

import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import WelcomeSlide from '@app/views/organism/Form/WelcomeSlide';

export default function FormPage({
    params
}: {
    params: { formId: string; workspaceName: string };
}) {
    const { formResponse, nextSlide, previousSlide } = useFormResponse();
    const { formId, workspaceName } = params;
    const { setStandardForm, standardForm } = useStandardForm();


    useEffect(() => {
        const forms = JSON.parse(localStorage.getItem('forms') || '{}');
        const currentForm = forms[formId];
        if (currentForm) {
            setStandardForm(currentForm);
        }
    }, []);

    const renderSlideComponent = () => {
        return <>We will render {formResponse.currentSlide + 1}th slide here.</>;
    };

    return (
        <div className="h-screen w-screen">
            {formResponse?.currentSlide === -1 && <WelcomeSlide />}
            {formResponse?.currentSlide === -2 && <div>This will be End Slide</div>}
            {formResponse?.currentSlide >= 0 && <div>{renderSlideComponent()}</div>}
        </div>
    );
}

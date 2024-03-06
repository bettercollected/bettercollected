'use client';

import { useEffect } from 'react';

import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import FormSlide from '@app/views/organism/Form/FormSlide';
import ThankyouPage from '@app/views/organism/Form/ThankyouPage';
import WelcomePage from '@app/views/organism/Form/WelcomePage';

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
            {formResponse?.currentSlide === -1 && <WelcomePage />}
            {formResponse?.currentSlide === -2 && <ThankyouPage />}
            {formResponse?.currentSlide >= 0 && (
                <FormSlide index={formResponse.currentSlide} />
            )}
        </div>
    );
}

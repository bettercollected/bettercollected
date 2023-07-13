import React, { useEffect, useState } from 'react';

import BetterCollectedForm from '@Components/Form/BetterCollectedForm';

import { Close } from '@app/components/icons/close';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { initialIBuilderState } from '@app/store/forms/slice';

import { useFullScreenModal } from '../full-screen-modal-context';

interface IFormBuilderPreviewModal {
    form: IBuilderState;
}

export default function FormBuilderPreviewModal({ form }: IFormBuilderPreviewModal) {
    const [formToRender, setFormToRender] = useState(initialIBuilderState);
    const { closeModal } = useFullScreenModal();

    useEffect(() => {
        if (form) {
            const previewForm: any = {};
            previewForm.title = form.title;
            previewForm.description = form.description;
            let fields: any = Object.values(form.fields);
            fields = fields.map((field: IFormFieldState) => {
                if (field.properties?.choices) {
                    return {
                        ...field,
                        properties: { ...field.properties, choices: Object.values(field.properties?.choices) }
                    };
                }
                return field;
            });
            previewForm.fields = fields;

            setFormToRender(previewForm);
        }
    }, [form]);

    return (
        <div className="relative h-full w-full overflow-auto pt-10 !bg-white ">
            <div
                className="absolute cursor-pointer text-black-600 top-10 right-10"
                onClick={() => {
                    closeModal();
                }}
            >
                {' '}
                Back to Editor
            </div>
            <BetterCollectedForm form={formToRender} />
        </div>
    );
}

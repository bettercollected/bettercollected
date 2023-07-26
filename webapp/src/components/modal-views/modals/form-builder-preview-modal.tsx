import React, { useEffect, useState } from 'react';

import BetterCollectedForm from '@Components/Form/BetterCollectedForm';

import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { initialIBuilderState } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';

import { useFullScreenModal } from '../full-screen-modal-context';

export default function FormBuilderPreviewModal() {
    const [formToRender, setFormToRender] = useState(initialIBuilderState);
    const { closeModal } = useFullScreenModal();
    const builderState = useAppSelector(selectBuilderState);

    useEffect(() => {
        if (builderState) {
            const previewForm: any = {};
            previewForm.title = builderState.title;
            previewForm.description = builderState.description;
            let fields: any = Object.values(builderState.fields);
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
    }, [builderState]);

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
            <BetterCollectedForm form={formToRender} enabled={true} preview={true} closeModal={closeModal} />
        </div>
    );
}

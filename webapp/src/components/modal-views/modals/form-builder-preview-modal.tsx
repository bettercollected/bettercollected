import React, {useEffect, useState} from 'react';

import EditIcon from '@Components/Common/Icons/Edit';
import Share from '@Components/Common/Icons/Share';
import Button from '@Components/Common/Input/Button';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';

import {formConstant} from '@app/constants/locales/form';
import {selectBuilderState} from '@app/store/form-builder/selectors';
import {IFormFieldState} from '@app/store/form-builder/types';
import {initialIBuilderState} from '@app/store/forms/slice';
import {useAppSelector} from '@app/store/hooks';
import {getFormUrl} from '@app/utils/urlUtils';

import {useFullScreenModal} from '../full-screen-modal-context';

export default function FormBuilderPreviewModal({publish}: { publish: () => void }) {
    const [formToRender, setFormToRender] = useState(initialIBuilderState);
    const {closeModal} = useFullScreenModal();
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
                        properties: {...field.properties, choices: Object.values(field.properties?.choices)}
                    };
                }
                return field;
            });
            previewForm.fields = fields;
            previewForm.buttonText = builderState.buttonText
            previewForm.settings = {
                responseDataOwnerField: builderState.settings?.responseDataOwnerField || ''
            };
            setFormToRender(previewForm);
        }
    }, [builderState]);

    return (
        <div className="relative w-full   !bg-brand-100 ">
            <div className="flex fixed z-[10000] bg-transparent top-6 right-10 gap-4 w-fit">
                <Button
                    variant="contained"
                    className="w-fit capitalize bg-brand-500 px-4 gap-2 py-2 "
                    onClick={() => {
                        closeModal();
                    }}
                    size="small"
                >
                    <span>
                        <EditIcon/>
                    </span>
                    Edit Form
                </Button>

                <Button
                    variant="outlined"
                    className="w-fit capitalize bg-brand-100 text-brand-500 px-4 gap-2 py-2 "
                    onClick={() => {
                        publish();
                    }}
                    size="small"
                >
                    Publish Form
                </Button>
            </div>
            <div className="h-screen overflow-auto 2xl:pt-6 min-h-screen w-full pt-28 pb-6 px-5">
                <BetterCollectedForm form={formToRender} enabled={true} preview={true} closeModal={closeModal}/>
            </div>
        </div>
    );
}

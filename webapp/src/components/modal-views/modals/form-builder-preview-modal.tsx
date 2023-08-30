import React, {useEffect, useState} from 'react';

import EditIcon from '@Components/Common/Icons/Edit';
import UploadIcon from '@Components/Common/Icons/FormBuilder/UploadIcon';
import Share from '@Components/Common/Icons/Share';
import Button from '@Components/Common/Input/Button';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import useFormBuilderAtom from '@Components/FormBuilder/builderAtom';

import uploadImage from '@app/assets/images/upload.png';
import Back from '@app/components/icons/back';
import Image from '@app/components/ui/image';
import {formConstant} from '@app/constants/locales/form';
import {selectBuilderState} from '@app/store/form-builder/selectors';
import {IFormFieldState} from '@app/store/form-builder/types';
import {initialIBuilderState} from '@app/store/forms/slice';
import {useAppSelector} from '@app/store/hooks';
import {getFormUrl} from '@app/utils/urlUtils';

import {useFullScreenModal} from '../full-screen-modal-context';
import PoweredBy from "@app/components/ui/powered-by";
import {useCreateFormMutation, usePatchFormMutation, workspacesApi} from "@app/store/workspaces/api";
import LoadingIcon from "@Components/Common/Icons/Loading";

export default function FormBuilderPreviewModal({publish}: { publish: () => void }) {
    const [formToRender, setFormToRender] = useState(initialIBuilderState);
    const {closeModal} = useFullScreenModal();
    const builderState = useAppSelector(selectBuilderState);
    const {headerImages} = useFormBuilderAtom();

    const updateRequest = useAppSelector(state1 => state1.workspacesApi.mutations)

    const isLoading = updateRequest && updateRequest[Object.keys(updateRequest)[Object.keys(updateRequest).length - 1]]?.status === "pending"

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
            previewForm.buttonText = builderState.buttonText;
            previewForm.settings = {
                responseDataOwnerField: builderState.settings?.responseDataOwnerField || ''
            };
            previewForm.coverImage = headerImages.coverImage ? URL.createObjectURL(headerImages?.coverImage) : builderState?.coverImage;
            previewForm.logo = headerImages.logo ? URL.createObjectURL(headerImages.logo) : builderState?.logo;
            setFormToRender(previewForm);

        }
    }, [builderState, headerImages]);

    return (
        <div className=" w-full">
            <div
                className="fixed z-[10000] h-[46px] border-b border-black-300 shadow px-5 !bg-white flex justify-between items-center top-0 right-0 left-0 gap-4">
                <div
                    className="flex items-center gap-2 text-black-800 text-[14px] cursor-pointer"
                    onClick={() => {
                        closeModal();
                    }}
                >
                    <Back/>
                    Back to Editor
                </div>
                <div
                    className="flex gap-2 items-center cursor-pointer"
                    onClick={() => {
                        publish();
                    }}
                >
                    {
                        isLoading ?
                            <LoadingIcon/> :
                            <UploadIcon/>
                    }
                    Publish
                </div>
            </div>
            <div className="h-screen overflow-auto min-h-screen w-full pt-10 pb-6">
                <BetterCollectedForm form={formToRender} enabled={true} preview={true} closeModal={closeModal}/>
            </div>
            <PoweredBy/>
        </div>
    );
}

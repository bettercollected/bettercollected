import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import UploadIcon from '@Components/Common/Icons/FormBuilder/UploadIcon';
import LoadingIcon from '@Components/Common/Icons/Loading';
import PublishIcon from '@Components/Common/Icons/PublishIcon';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import ThankYouPage from '@Components/Form/ThankYouPage';
import useFormBuilderAtom from '@Components/FormBuilder/builderAtom';
import { toast } from 'react-toastify';

import Back from '@app/components/icons/back';
import PoweredBy from '@app/components/ui/powered-by';
import { selectConsentState } from '@app/store/consent/selectors';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { initFormState, selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useCreateTemplateFromFormMutation } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import { useFullScreenModal } from '../full-screen-modal-context';

export default function FormBuilderPreviewModal({ publish, isFormSubmitted = false, imagesRemoved = {} }: { publish: () => void; isFormSubmitted: boolean; imagesRemoved: any }) {
    const [formToRender, setFormToRender] = useState(initFormState);
    const { closeModal } = useFullScreenModal();
    const builderState = useAppSelector(selectBuilderState);
    const consentState = useAppSelector(selectConsentState);
    const { headerImages } = useFormBuilderAtom();
    const router = useRouter();

    const updateRequest = useAppSelector((state1) => state1.workspacesApi.mutations);

    const isLoading = updateRequest && updateRequest[Object.keys(updateRequest)[Object.keys(updateRequest).length - 1]]?.status === 'pending';

    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);

    const [createFormAsTemplate] = useCreateTemplateFromFormMutation();

    const makeTemplate = async () => {
        try {
            const request = {
                workspace_id: workspace.id,
                form_id: form.formId
            };
            const response: any = await createFormAsTemplate(request);
            if (response?.data) {
                toast('Created Successfully', { type: 'success' });
                router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };

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
            previewForm.buttonText = builderState.buttonText;
            previewForm.settings = {
                responseDataOwnerField: builderState.settings?.responseDataOwnerField || ''
            };
            if (!imagesRemoved.cover) previewForm.coverImage = headerImages.coverImage ? URL.createObjectURL(headerImages?.coverImage) : builderState?.coverImage;
            if (!imagesRemoved.logo) previewForm.logo = headerImages.logo ? URL.createObjectURL(headerImages.logo) : builderState?.logo;
            previewForm.consent = consentState.consents;
            setFormToRender(previewForm);
        }
    }, [builderState, headerImages]);

    return (
        <div className=" w-full">
            <div className="fixed z-[10000] h-[46px] border-b border-black-300 shadow px-5 !bg-white flex justify-between items-center top-0 right-0 left-0 gap-4">
                <div
                    className="flex items-center gap-2 text-black-800 text-[14px] cursor-pointer"
                    onClick={() => {
                        closeModal();
                    }}
                >
                    <Back />
                    Back to Editor
                </div>
                <div className={'flex flex-row gap-4'}>
                    <AppButton variant={ButtonVariant.Secondary} onClick={makeTemplate}>
                        Make Template
                    </AppButton>
                    <AppButton icon={<PublishIcon />} onClick={publish}>
                        Publish Form
                    </AppButton>
                </div>
                {/*<div*/}
                {/*    className="flex gap-2 items-center cursor-pointer"*/}
                {/*    onClick={() => {*/}
                {/*        publish();*/}
                {/*    }}*/}
                {/*>*/}
                {/*    {isLoading ? <LoadingIcon /> : <UploadIcon />}*/}
                {/*    Publish*/}
                {/*</div>*/}
            </div>
            <div className="h-screen overflow-auto min-h-screen w-full pt-10 pb-6">{isFormSubmitted ? <ThankYouPage isDisabled={true} /> : <BetterCollectedForm form={formToRender} enabled={true} isPreview={true} closeModal={closeModal} />}</div>
            {(!workspace?.isPro || !form?.settings?.disableBranding) && <PoweredBy isFormCreatorPortal={true} />}
        </div>
    );
}

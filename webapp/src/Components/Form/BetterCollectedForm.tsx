import React, { useEffect, useState } from 'react';

import Image from 'next/image';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MarkdownText from '@Components/Common/Markdown';
import CheckboxField from '@Components/Form/CheckboxField';
import DropdownField from '@Components/Form/DropdownField';
import FieldValidations from '@Components/Form/FieldValidations';
import FileUpload from '@Components/Form/FileUpload';
import LongText from '@Components/Form/LongText';
import MultipleChoiceField from '@Components/Form/MultipleChoiceField';
import PhoneNumber from '@Components/Form/PhoneNumber';
import RankingField from '@Components/Form/RankingField';
import RatingField from '@Components/Form/RatingField';
import ShortText from '@Components/Form/ShortText';
import ThankYouPage from '@Components/Form/ThankYouPage';
import { toast } from 'react-toastify';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { ConsentAnswerDto } from '@app/store/consent/types';
import { resetFillForm, selectAnswers, selectFormResponderOwnerField, selectInvalidFields, setDataResponseOwnerField, setInvalidFields } from '@app/store/fill-form/slice';
import { FormValidationError } from '@app/store/fill-form/type';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useSubmitResponseMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';
import { validateFormFieldAnswer } from '@app/utils/validationUtils';

import useFormAtom from './atom';

export interface FormFieldProps {
    field: StandardFormFieldDto;
    ans?: any;
    enabled?: boolean;
}

const renderFormField = (field: StandardFormFieldDto, enabled?: boolean, answer?: any) => {
    switch (field?.type) {
        case FormBuilderTagNames.LAYOUT_SHORT_TEXT:
        case FormBuilderTagNames.LAYOUT_HEADER3:
        case FormBuilderTagNames.LAYOUT_HEADER1:
        case FormBuilderTagNames.LAYOUT_HEADER4:
        case FormBuilderTagNames.LAYOUT_HEADER2:
        case FormBuilderTagNames.LAYOUT_LABEL:
            return <div className={contentEditableClassNames(false, field?.type, enabled) + ' mt-6 '}>{field?.value}</div>;
        case FormBuilderTagNames.LAYOUT_MARKDOWN:
            return <MarkdownText text={field.value ?? ''} />;
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
        case FormBuilderTagNames.INPUT_EMAIL:
        case FormBuilderTagNames.INPUT_NUMBER:
        case FormBuilderTagNames.INPUT_LINK:
            return <ShortText enabled={enabled} field={field} ans={answer} />;
        case FormBuilderTagNames.INPUT_DATE:
            return <ShortText enabled={enabled} field={field} ans={answer} helperText={field?.properties?.placeholder} />;
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return <PhoneNumber enabled={enabled} field={field} ans={answer} />;
        case FormBuilderTagNames.INPUT_LONG_TEXT:
            return <LongText field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
            return <MultipleChoiceField field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_CHECKBOXES:
            return <CheckboxField field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_DROPDOWN:
            return <DropdownField field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_RANKING:
            return <RankingField field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_MEDIA:
            return <FileUpload field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_RATING:
            return <RatingField field={field} ans={answer} enabled={enabled} />;
        default:
            return <></>;
    }
};

interface IBetterCollectedFormProps {
    form: StandardFormDto;
    enabled?: boolean;
    isCustomDomain?: boolean;
    response?: StandardFormResponseDto;
    isPreview?: boolean;
    closeModal?: () => void;
    isDisabled?: boolean;
    isTemplate?: boolean;
}

export default function BetterCollectedForm({ form, enabled = false, response, isCustomDomain = false, isPreview = false, closeModal, isDisabled = false, isTemplate = false }: IBetterCollectedFormProps) {
    const dispatch = useAppDispatch();
    const { openModal, closeModal: closeFullScreenModal } = useFullScreenModal();
    const [submitResponse] = useSubmitResponseMutation();
    const answers = useAppSelector(selectAnswers);
    const responseDataOwnerField = useAppSelector(selectFormResponderOwnerField);
    const invalidFields = useAppSelector(selectInvalidFields);
    const workspace = useAppSelector(selectWorkspace);
    const { files, resetFormFiles } = useFormAtom();

    const [isFormSubmitted, setIsFormSubmitted] = useState(false);

    useEffect(() => {
        dispatch(resetFillForm());

        return () => {
            dispatch(resetFillForm());
        };
    }, []);

    useEffect(() => {
        dispatch(setDataResponseOwnerField(form?.settings?.responseDataOwnerField || ''));
    }, [form]);

    const [isResponseValid, setResponseValid] = useState(true);

    const onFormSubmitCallback = async (consentAnswers: Record<string, ConsentAnswerDto>) => {
        if (isPreview) {
            openModal('FORM_BUILDER_PREVIEW', { isFormSubmitted: true });
            return;
        }
        const formData = new FormData();
        // Append files to formData
        files.forEach((fileObj) => {
            formData.append('files', fileObj.file, fileObj.fileName);
            formData.append('file_field_ids', fileObj.fieldId);
            formData.append('file_ids', fileObj.fileId);
        });
        const responseExpirationType = form?.settings?.responseExpirationType;
        const responseExpiration = form?.settings?.responseExpiration;

        let responseExpirationTime = '';
        if (responseExpirationType === 'date') {
            responseExpirationTime = new Date(responseExpiration || '').toISOString();
        } else if (responseExpirationType === 'days') {
            const expiryDate = new Date();
            expiryDate.setDate(expiryDate.getDate() + parseInt(responseExpiration || ''));
            responseExpirationTime = expiryDate.toISOString();
        }

        const postBody = {
            form_id: form?.formId,
            answers: answers,
            form_version: form?.version || 1,
            consent: Object.values(consentAnswers),
            expiration: responseExpirationTime,
            expirationType: responseExpirationType,
            dataOwnerIdentifier: (answers && answers[responseDataOwnerField]?.email) || null
        };

        formData.append('response', JSON.stringify(postBody));

        const response: any = await submitResponse({ workspaceId: workspace.id, formId: form?.formId, body: formData });
        if (response?.data) {
            resetFormFiles();
            dispatch(resetFillForm());
            setIsFormSubmitted(true);
        } else {
            toast('Error submitting response', { type: 'error' });
        }
        closeFullScreenModal();
    };
    const onSubmitForm = async (event: any) => {
        event.preventDefault();
        if (isTemplate) return;
        const invalidFields: Record<string, Array<FormValidationError>> = {};
        let isResponseValid = true;
        form?.fields.forEach((field: StandardFormFieldDto, index: number) => {
            const validationErrors = validateFormFieldAnswer(field, answers[field.id]);
            if (validationErrors.length > 0) {
                setResponseValid(false);
                isResponseValid = false;
            }
            invalidFields[field.id] = validationErrors;
        });

        if (!isResponseValid) {
            dispatch(setInvalidFields(invalidFields));
            let firstInvalidFieldId = '';
            for (let field of form.fields) {
                if (Object.keys(invalidFields).includes(field.id) && invalidFields[field.id].length > 0) {
                    firstInvalidFieldId = field.id;
                    break;
                }
            }
            console.log(firstInvalidFieldId);
            document.getElementById(firstInvalidFieldId)?.scrollIntoView({
                behavior: 'smooth',
                inline: 'center',
                block: 'center'
            });
            const errorInputDiv = document.getElementById(`input-${firstInvalidFieldId}`);
            errorInputDiv?.focus({ preventScroll: true });
            return;
        }
        setResponseValid(true);
        if (isPreview) {
            openModal('CONSENT_FULL_MODAL_VIEW', { form: form, isPreview: true, onFormSubmit: onFormSubmitCallback });
            return;
        }
        openModal('CONSENT_FULL_MODAL_VIEW', { form: form, onFormSubmit: onFormSubmitCallback });
    };
    useEffect(() => {
        return () => {
            resetFillForm();
        };
    }, []);

    if (isFormSubmitted) {
        return <ThankYouPage isDisabled={isDisabled} />;
    }

    return (
        <div className="w-full bg-white">
            {form?.coverImage && (
                <div className={`relative z-0 w-full flex aspect-banner-mobile lg:aspect-banner-desktop`}>
                    <Image layout="fill" objectFit="cover" src={form.coverImage} alt="test" className="brightness-75" />
                </div>
            )}
            <form
                className="w-full max-w-[700px] mx-auto px-10 pb-10 bg-white flex rounded-lg flex-col items-start "
                onKeyDown={(event: any) => {
                    if (!event.shiftKey && event.key === 'Enter') {
                        event.preventDefault();
                    }
                }}
                onSubmit={onSubmitForm}
            >
                {form?.logo && (
                    <div className={`relative ${form?.coverImage ? '-top-12' : 'mt-[60px]'} rounded-lg w-[100px] h-[100px] flex flex-col justify-center items-center gap-3 cursor-pointer hover:shadow-logoCard`}>
                        <Image height={100} width={100} objectFit="cover" src={form.logo} alt="logo" className="rounded-lg hover:bg-black-100" />
                    </div>
                )}
                <div className={`mb-6 ${form?.coverImage && form?.logo ? '' : 'mt-12'}`}>
                    <div className="text-[24px] mb-2 font-semibold text-black-900">{form?.title}</div>
                    {form?.description && <div className="text-[14px] text-black-700">{form?.description}</div>}
                </div>

                <div className="flex flex-col w-full gap-2">
                    {form?.fields?.map((field: StandardFormFieldDto) => (
                        <div key={field?.id} className="relative w-full" id={field?.id}>
                            {renderFormField(field, enabled, response?.answers[field.id] || answers[field.id])}
                            <FieldValidations field={field} inValidations={invalidFields[field?.id]} />
                        </div>
                    ))}
                    <div>
                        {!isResponseValid && <div className="text-red-500 my-2 text-sm">*Invalid answers in one or more fields. Check and correct the highlighted entries.</div>}
                        <AppButton variant={ButtonVariant.Secondary} type="submit" disabled={!enabled}>
                            {form?.buttonText || 'Submit'}
                        </AppButton>
                    </div>
                </div>
            </form>
        </div>
    );
}

import React, { useEffect } from 'react';

import { useRouter } from 'next/router';

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
import cn from 'classnames';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import { StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
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
            return <div className={contentEditableClassNames(false, field?.type)}>{field?.value}</div>;
        case FormBuilderTagNames.LAYOUT_HEADER3:
        case FormBuilderTagNames.LAYOUT_HEADER1:
        case FormBuilderTagNames.LAYOUT_HEADER4:
        case FormBuilderTagNames.LAYOUT_HEADER2:
            return <div className={'!mt-8 ' + contentEditableClassNames(false, field?.type)}>{field?.value}</div>;
        case FormBuilderTagNames.LAYOUT_LABEL:
            return <div className={'!mt-3 ' + contentEditableClassNames(false, field?.type)}>{field?.value}</div>;
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
    preview?: boolean;
    closeModal?: () => void;
}

export default function BetterCollectedForm({ form, enabled = false, response, isCustomDomain = false, preview = false, closeModal }: IBetterCollectedFormProps) {
    const dispatch = useAppDispatch();
    const [submitResponse] = useSubmitResponseMutation();
    const answers = useAppSelector(selectAnswers);
    const responseDataOwnerField = useAppSelector(selectFormResponderOwnerField);
    const invalidFields = useAppSelector(selectInvalidFields);
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const { files, resetFormFiles } = useFormAtom();

    useEffect(() => {
        dispatch(resetFillForm());

        return () => {
            dispatch(resetFillForm());
        };
    }, [dispatch]);

    useEffect(() => {
        dispatch(setDataResponseOwnerField(form?.settings?.responseDataOwnerField || ''));
    }, [dispatch, form]);

    const onSubmitForm = async (event: any) => {
        event.preventDefault();
        const invalidFields: Record<string, Array<FormValidationError>> = {};
        let isResponseValid = true;
        form?.fields.forEach((field: StandardFormFieldDto, index: number) => {
            const validationErrors = validateFormFieldAnswer(field, answers[field.id]);
            if (validationErrors.length > 0) {
                isResponseValid = false;
            }
            invalidFields[field.id] = validationErrors;
        });

        if (!isResponseValid) {
            dispatch(setInvalidFields(invalidFields));
            // toast('All required fields are not filled yet.', { type: 'error' });
            return;
        }
        if (preview) {
            toast('Response Submitted', { type: 'success' });
            closeModal && closeModal();
            return;
        }

        const formData = new FormData();
        console.log(files);
        // Append files to formData
        files.forEach((fileObj) => {
            formData.append('files', fileObj.file, fileObj.fileName);
            formData.append('file_field_ids', fileObj.fieldId);
            formData.append('file_ids', fileObj.fileId);
        });

        const postBody = {
            form_id: form?.formId,
            answers: answers,
            dataOwnerIdentifier: (answers && answers[responseDataOwnerField]?.email) || null
        };
        formData.append('response', JSON.stringify(postBody));
        console.log(formData);
        const response: any = await submitResponse({ workspaceId: workspace.id, formId: form?.formId, body: formData });
        if (response?.data) {
            toast('Response Submitted', { type: 'success' });
            resetFormFiles();
            const workspaceUrl = isCustomDomain ? `https://${workspace.customDomain}` : `/${workspace.workspaceName}`;
            router.push(workspaceUrl);
        } else {
            toast('Error submitting response', { type: 'error' });
        }
    };
    useEffect(() => {
        return () => {
            resetFillForm();
        };
    });

    return (
        <form
            className="w-full max-w-[700px] mx-auto px-10 py-10 bg-white flex rounded-lg flex-col items-start "
            onKeyDown={(event: any) => {
                if (!event.shiftKey && event.key === 'Enter') {
                    event.preventDefault();
                }
            }}
            onSubmit={onSubmitForm}
        >
            <div className="mb-7">
                <div className="text-[24px] mb-3 font-semibold text-black-900">{form?.title}</div>
                {form?.description && <div className="text-[14px] text-black-700">{form?.description}</div>}
            </div>

            <div className="flex flex-col w-full gap-2">
                {form?.fields.map((field: StandardFormFieldDto) => (
                    <div key={field?.id} className="relative w-full">
                        {renderFormField(field, enabled, response?.answers[field.id] || answers[field.id])}
                        <FieldValidations field={field} inValidations={invalidFields[field?.id]} />
                    </div>
                ))}
                <div>
                    <button className={cn('mt-10 py-3 text-white rounded min-w-[130px] px-5 !text-[14px] bg-black-900  !font-semibold ', enabled ? 'cursor-pointer' : 'cursor-not-allowed')} type="submit" disabled={!enabled}>
                        {form?.buttonText || 'Submit'}
                    </button>
                </div>
            </div>
        </form>
    );
}

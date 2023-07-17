import React, { useEffect } from 'react';

import { useRouter } from 'next/router';

import CheckboxField from '@Components/Form/CheckboxField';
import DropdownField from '@Components/Form/DropdownField';
import LongText from '@Components/Form/LongText';
import MultipleChoiceField from '@Components/Form/MultipleChoiceField';
import RankingField from '@Components/Form/RankingField';
import RatingField from '@Components/Form/RatingField';
import ShortText from '@Components/Form/ShortText';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import { StandardFormDto, StandardFormQuestionDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { resetFillForm, selectAnswers, selectInvalidFields, selectRequiredFields, setInvalidFields, setRequiredFields } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useSubmitResponseMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';

export interface FormFieldProps {
    field: StandardFormQuestionDto;
    ans?: any;
    enabled?: boolean;
}

const renderFormField = (field: StandardFormQuestionDto, enabled?: boolean, answer?: any) => {
    switch (field?.type) {
        case FormBuilderTagNames.LAYOUT_SHORT_TEXT:
        case FormBuilderTagNames.LAYOUT_HEADER3:
        case FormBuilderTagNames.LAYOUT_HEADER1:
        case FormBuilderTagNames.LAYOUT_HEADER4:
        case FormBuilderTagNames.LAYOUT_HEADER2:
        case FormBuilderTagNames.LAYOUT_HEADER5:
        case FormBuilderTagNames.LAYOUT_LABEL:
            return <div className={'mt-5 ' + contentEditableClassNames(false, field?.type)}>{field?.value}</div>;
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
        case FormBuilderTagNames.INPUT_EMAIL:
        case FormBuilderTagNames.INPUT_NUMBER:
        case FormBuilderTagNames.INPUT_LINK:
        case FormBuilderTagNames.INPUT_DATE:
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return <ShortText enabled={enabled} field={field} ans={answer} />;
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
    const invalidFields = useAppSelector(selectInvalidFields);
    const requiredFields = useAppSelector(selectRequiredFields);
    const [submitResponse] = useSubmitResponseMutation();
    const answers = useAppSelector(selectAnswers);
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();

    useEffect(() => {
        const requiredFields: Array<string> = [];
        for (const field of form?.fields || []) {
            if (field?.validations?.required) {
                requiredFields.push(field.id);
            }
        }
        dispatch(setRequiredFields(requiredFields));
    }, [form]);

    useEffect(() => {
        dispatch(resetFillForm());
    }, []);

    const onSubmitForm = async (event: any) => {
        event.preventDefault();
        const invalidFields: Array<string> = [];
        for (const requiredField of requiredFields) {
            if (!answers[requiredField]) {
                invalidFields.push(requiredField);
            }
        }
        if (invalidFields.length > 0) {
            dispatch(setInvalidFields(invalidFields));
            // toast('All required fields are not filled yet.', { type: 'error' });
            return;
        }
        if (preview) {
            toast('Response Submitted', { type: 'success' });
            closeModal && closeModal();
            return;
        }
        const postBody = {
            form_id: form?.formId,
            answers: answers
        };
        const response: any = await submitResponse({ workspaceId: workspace.id, formId: form?.formId, body: postBody });
        if (response?.data) {
            toast('Response Submitted', { type: 'success' });
            const workspaceUrl = isCustomDomain ? `https://${workspace.customDomain}` : `/${workspace.workspaceName}`;
            router.push(workspaceUrl);
        } else {
            toast('Error submitting response', { type: 'error' });
        }
    };

    return (
        <form
            className="w-full max-w-[700px] mx-auto px-10 lg:px-0 py-10 bg-white flex flex-col items-start "
            onKeyDown={(event: any) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                }
            }}
            onSubmit={onSubmitForm}
        >
            <div>
                <div className="text-[36px] font-bold">{form?.title}</div>
            </div>
            {form?.fields.map((field: StandardFormQuestionDto) => (
                <div key={field?.id} className="relative w-full">
                    {renderFormField(field, enabled, response?.answers[field.id])}
                    {invalidFields?.includes(field?.id) && <div className="text-red-500 mt-2">Field Required*</div>}
                    {field?.validations?.required && (
                        <>
                            <div className="absolute top-1  cursor-pointer  rounded-full">
                                <span className="!w-4 text-center flex items-center justify-center pt-1.5 text-xl font-bold rounded-full !h-4 relative -left-2  bg-gray-300 px-0.5  z-[35003]">*</span>
                            </div>
                        </>
                    )}
                </div>
            ))}
            <Button className="mt-10" type="submit" disabled={!enabled}>
                Submit
            </Button>
        </form>
    );
}

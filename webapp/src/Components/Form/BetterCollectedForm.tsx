import { useEffect } from 'react';

import CheckboxField from '@Components/Form/CheckboxField';
import DropdownField from '@Components/Form/DropdownField';
import LongText from '@Components/Form/LongText';
import MultipleChoiceField from '@Components/Form/MultipleChoiceField';
import RankingField from '@Components/Form/RankingField';
import RatingField from '@Components/Form/RatingField';
import ShortText from '@Components/Form/ShortText';
import FieldRequiredIcon from '@Components/FormBuilder/FieldRequiredIcon';

import { StandardFormDto, StandardFormQuestionDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { resetFillForm, selectInvalidFields } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';

export interface FormFieldProps {
    field: StandardFormQuestionDto;
    ans?: any;
    enabled?: boolean;
}

const renderFormField = (field: StandardFormQuestionDto, enabled?: boolean, answer?: any) => {
    switch (field?.tag) {
        case FormBuilderTagNames.LAYOUT_SHORT_TEXT:
        case FormBuilderTagNames.LAYOUT_HEADER3:
        case FormBuilderTagNames.LAYOUT_HEADER1:
        case FormBuilderTagNames.LAYOUT_HEADER4:
        case FormBuilderTagNames.LAYOUT_HEADER2:
        case FormBuilderTagNames.LAYOUT_HEADER5:
        case FormBuilderTagNames.LAYOUT_LABEL:
            return <div className={'mt-5 ' + contentEditableClassNames(false, field?.tag)}>{field?.value}</div>;
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

export default function BetterCollectedForm({ form, enabled = false, response }: { form: StandardFormDto; enabled?: boolean; response?: StandardFormResponseDto }) {
    const dispatch = useAppDispatch();
    const invalidFields = useAppSelector(selectInvalidFields);

    useEffect(() => {
        dispatch(resetFillForm);
    }, []);
    return (
        <div className="w-full max-w-[700px] mx-auto px-10 lg:px-0 py-10">
            <div>
                <div className="text-[36px] font-bold">{form?.title}</div>
            </div>
            {form?.fields.map((field: StandardFormQuestionDto) => (
                <div key={field?.id} className="relative">
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
        </div>
    );
}

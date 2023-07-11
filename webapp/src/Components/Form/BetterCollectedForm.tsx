import CheckboxField from '@Components/Form/CheckboxField';
import DropdownField from '@Components/Form/DropdownField';
import LongText from '@Components/Form/LongText';
import MultipleChoiceField from '@Components/Form/MultipleChoiceField';
import RankingField from '@Components/Form/RankingField';
import RatingField from '@Components/Form/RatingField';
import ShortText from '@Components/Form/ShortText';
import TextField from '@mui/material/TextField';

import { StandardFormDto, StandardFormQuestionDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';

export interface FormFieldProps {
    field: StandardFormQuestionDto;
    ans?: any;
    enabled?: boolean;
}

const renderFormField = (field: StandardFormQuestionDto, answer?: any) => {
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
            return <ShortText enabled field={field} ans={answer} />;
        case FormBuilderTagNames.INPUT_LONG_TEXT:
            return <LongText field={field} ans={answer} enabled />;
        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
            return <MultipleChoiceField field={field} enabled />;
        case FormBuilderTagNames.INPUT_CHECKBOXES:
            return <CheckboxField field={field} />;
        case FormBuilderTagNames.INPUT_DROPDOWN:
            return <DropdownField field={field} />;
        case FormBuilderTagNames.INPUT_RANKING:
            return <RankingField field={field} />;
        case FormBuilderTagNames.INPUT_RATING:
            return <RatingField field={field} />;

        default:
            return <></>;
    }
};

export default function BetterCollectedForm({ form }: { form: StandardFormDto }) {
    return (
        <div
            className="w-full max-w-4xl mx-auto px-10 lg:px-0
         py-10"
        >
            <div>
                <div className="text-[36px] font-bold">{form?.title}</div>
            </div>
            {form?.fields.map((field: StandardFormQuestionDto) => (
                <div key={field?.id}>{renderFormField(field)}</div>
            ))}
        </div>
    );
}

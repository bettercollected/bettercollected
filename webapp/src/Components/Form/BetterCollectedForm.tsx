import CheckboxField from '@Components/Form/CheckboxField';
import DropdownField from '@Components/Form/DropdownField';
import MultipleChoiceField from '@Components/Form/MultipleChoiceField';
import TextField from '@mui/material/TextField';

import BetterInput from '@app/components/Common/input';
import { StandardFormDto, StandardFormQuestionDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';

const renderFormField = (field: StandardFormQuestionDto) => {
    switch (field?.tag) {
        case FormBuilderTagNames.LAYOUT_SHORT_TEXT:
        case FormBuilderTagNames.LAYOUT_HEADER3:
        case FormBuilderTagNames.LAYOUT_HEADER1:
        case FormBuilderTagNames.LAYOUT_HEADER4:
        case FormBuilderTagNames.LAYOUT_HEADER2:
        case FormBuilderTagNames.LAYOUT_HEADER5:
        case FormBuilderTagNames.LAYOUT_LABEL:
            return <div className={contentEditableClassNames(false, field?.tag)}>{field?.value}</div>;
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
        case FormBuilderTagNames.INPUT_EMAIL:
        case FormBuilderTagNames.INPUT_NUMBER:
        case FormBuilderTagNames.INPUT_LINK:
        case FormBuilderTagNames.INPUT_DATE:
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return <BetterInput />;
        case FormBuilderTagNames.INPUT_LONG_TEXT:
            return <TextField className="w-full mb-3 bg-white" multiline minRows={3} maxRows={10} />;
        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
            return <MultipleChoiceField field={field} />;
        case FormBuilderTagNames.INPUT_CHECKBOXES:
            return <CheckboxField field={field} />;
        case FormBuilderTagNames.INPUT_DROPDOWN:
            return <DropdownField field={field} />;

        default:
            return <></>;
    }
};

export default function BetterCollectedForm({ form }: { form: StandardFormDto }) {
    return (
        <>
            <div className="max-w-[900px]">
                <div className="text-[36px] font-bold">{form?.title}</div>
            </div>
            {form?.fields.map((field: StandardFormQuestionDto) => (
                <div key={field?.id}>{renderFormField(field)}</div>
            ))}
        </>
    );
}

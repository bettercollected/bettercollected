import BetterInput from '@app/components/Common/input';
import { StandardFormQuestionDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

const getInputType = (tag?: FormBuilderTagNames) => {
    switch (tag) {
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return 'tel';
        case FormBuilderTagNames.INPUT_EMAIL:
            return 'email';
        case FormBuilderTagNames.INPUT_NUMBER:
            return 'number';
        case FormBuilderTagNames.INPUT_DATE:
            return 'date';
        default:
            return 'text';
    }
};
export default function TextInputField({ field }: { field: StandardFormQuestionDto }) {
    return (
        <div>
            <BetterInput type={getInputType(field?.tag)} required={field?.validations?.required} placeholder={field?.properties?.placeholder || ''} />
        </div>
    );
}

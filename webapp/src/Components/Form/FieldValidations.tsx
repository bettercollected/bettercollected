import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FormValidationError } from '@app/store/fill-form/type';

interface IFieldValidations {
    field: StandardFormFieldDto;
    inValidations: Array<FormValidationError>;
}

export const getErrorText = (field: StandardFormFieldDto, invalidation: FormValidationError) => {
    switch (invalidation) {
        case FormValidationError.REQUIRED:
            return 'Required';
        case FormValidationError.REGEX_PATTERN:
            return 'Invalid Pattern';
        case FormValidationError.EXCEEDS_MAX_VALUE:
            return "Value can't be greater than " + field?.validations?.maxValue;
        case FormValidationError.INSUFFICIENT_VALUE:
            return "Value can't be less than " + field?.validations?.minValue;
        case FormValidationError.EXCEEDS_MAX_LENGTH:
            return 'Max allowed characters is ' + field?.validations?.maxLength;
        case FormValidationError.INSUFFICIENT_LENGTH:
            return 'Min required characters is ' + field?.validations?.minLength;
        case FormValidationError.EXCEEDS_MAX_CHOICES:
            return 'Max choices allowed is ' + field?.validations?.maxChoices;
        case FormValidationError.INSUFFICIENT_CHOICES:
            return 'Min required choices is ' + FormValidationError.INSUFFICIENT_CHOICES;
        default:
            return '';
    }
};

export default function FieldValidations({ field, inValidations }: IFieldValidations) {
    if (!inValidations?.length) return <></>;
    return (
        <div className="body4 !text-red-500 !my-2">
            {Object.values(FormValidationError).map((invalidation, index) => (
                <>{inValidations?.includes(invalidation) && <div className="flex flex-col gap-2">*{getErrorText(field, invalidation)}</div>}</>
            ))}
        </div>
    );
}
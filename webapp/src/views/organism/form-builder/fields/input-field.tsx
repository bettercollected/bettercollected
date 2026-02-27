import FieldInputWrapper from '@Components/hocs/field-input-wrapper';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { getPlaceholderValueForField } from '@app/utils/form-utils';

const InputField = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { updateFieldPlaceholder } = useFormFieldsAtom();
    const { theme } = useFormState();

    return (
        <>
            <FieldInputWrapper
                style={{ color: slide.properties?.theme?.tertiary || theme?.tertiary }}
                slide={slide}
                disabled={disabled}
                value={field.properties?.placeholder}
                placeholder={getPlaceholderValueForField(field?.type || FieldTypes.SHORT_TEXT)}
                onChange={(value: any) => updateFieldPlaceholder(field.index, slide.index, value)}
            />
        </>
    );
};

export default InputField;

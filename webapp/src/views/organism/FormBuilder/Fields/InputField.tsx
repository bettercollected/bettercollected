import FieldInputWrapper from '@Components/HOCs/FieldInputWrapper';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { getPlaceholderValueForField } from '@app/utils/formUtils';

const InputField = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { updateFieldPlaceholder } = useFormFieldsAtom();

    return (
        <>
            <FieldInputWrapper
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

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { getPlaceholderValueForField } from '@app/utils/formUtils';

const InputField = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { updateFieldPlaceholder } = useFormFieldsAtom();
    const { theme } = useFormState();

    return (
        <>
            <FieldInput
                $slide={slide}
                type="text"
                value={field.properties?.placeholder}
                style={{
                    color: slide?.properties?.theme?.tertiary || theme?.tertiary
                }}
                placeholder={getPlaceholderValueForField(field.type || FieldTypes.SHORT_TEXT)}
                onChange={(e: any) => updateFieldPlaceholder(field.index, slide.index, e.target.value)}
            />
        </>
    );
};

export default InputField;

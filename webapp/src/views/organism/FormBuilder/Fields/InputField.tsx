import FieldInputWrapper from '@Components/HOCs/FieldInputWrapper';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';

const InputField = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { updateFieldPlaceholder } = useFormFieldsAtom();

    return (
        <>
            <FieldInputWrapper field={field} slide={slide} disabled={disabled} value={field.properties?.placeholder} onChange={(value: any) => updateFieldPlaceholder(field.index, slide.index, value)} />
        </>
    );
};

export default InputField;



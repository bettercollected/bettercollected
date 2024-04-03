import { FormField } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';


export default function FieldDescription({
    field,
    disabled = false
}: {
    field: FormField;
    disabled?: boolean;
}) {
    const { activeSlide: slide, updateDescription } = useFormFieldsAtom();
    if (field?.description !== null && field?.description !== undefined) {
        return (
            <input
                id={`input-${disabled ? `${slide!.id}${field.id}` : field.id}`}
                placeholder={'Enter description'}
                className={
                    'text-md ring-none -left-1 mt-1 w-full border-0 !bg-inherit px-0 py-0 text-black-800 outline-none '
                }
                type="text"
                value={field.description}
                onChange={(e: any) =>
                    updateDescription(field.index, slide!.index, e.target.value)
                }
            />
        );
    }
    return null;
}
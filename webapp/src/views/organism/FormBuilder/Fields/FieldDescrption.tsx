import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { Textarea } from '@app/shadcn/components/ui/textarea';

export default function FieldDescription({ field, disabled = false }: { field: StandardFormFieldDto; disabled?: boolean }) {
    const { activeSlide: slide, updateDescription } = useFormFieldsAtom();
    if (field?.description !== null && field?.description !== undefined) {
        return (
            <Textarea
                rows={1}
                placeholder={'Enter description'}
                className={'text-md text-black-800 -left-1 mt-1 w-full border-0 !bg-inherit px-0 py-0 outline-none resize-none min-h-0 focus-visible:ring-0 shadow-none'}
                value={field.description}
                onChange={(e: any) => updateDescription(field.index, slide!.index, e.target.value)}
            />
        );
    }
    return null;
}

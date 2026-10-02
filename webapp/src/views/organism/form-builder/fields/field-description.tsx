import { StandardFormFieldDto } from '@app/models/dtos/form';
import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';

/** The question's description under its title: grows with its text instead of scrolling inside one line. */
export default function FieldDescription({ field, disabled = false }: { field: StandardFormFieldDto; disabled?: boolean }) {
    const { activeSlide: slide, updateDescription } = useFormFieldsAtom();
    if (field?.description !== null && field?.description !== undefined) {
        return (
            <AutosizeTextarea
                minHeight={24}
                disabled={disabled}
                placeholder={'Enter description'}
                aria-label="Question description"
                className={'text-md -left-1 mt-1 w-full resize-none overflow-hidden border-0 !bg-inherit px-0 py-0 text-black-800 shadow-none outline-none focus-visible:ring-0'}
                style={{ resize: 'none' }}
                value={field.description}
                onChange={(e: any) => updateDescription(field.index, slide!.index, e.target.value)}
            />
        );
    }
    return null;
}

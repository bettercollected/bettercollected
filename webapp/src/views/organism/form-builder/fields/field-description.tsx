import { StandardFormFieldDto } from '@app/models/dtos/form';
import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import PlainLanguageHints from '@app/views/molecules/form-builder/plain-language-hints';

export interface FieldDescriptionHints {
    formId?: string;
    formLanguage?: string | null;
}

/**
 * The question's description under its title: grows with its text instead of
 * scrolling inside one line. With `hints`, plain-language tips show under it.
 */
export default function FieldDescription({ field, disabled = false, hints }: { field: StandardFormFieldDto; disabled?: boolean; hints?: FieldDescriptionHints }) {
    const { activeSlide: slide, updateDescription } = useFormFieldsAtom();
    if (field?.description !== null && field?.description !== undefined) {
        const hintsId = `plain-language-description-${field.id}`;
        return (
            <>
                <AutosizeTextarea
                    minHeight={24}
                    disabled={disabled}
                    placeholder={'Enter description'}
                    aria-label="Question description"
                    aria-describedby={hints ? hintsId : undefined}
                    className={'text-md -left-1 mt-1 w-full resize-none overflow-hidden border-0 !bg-inherit px-0 py-0 text-black-800 shadow-none outline-none focus-visible:ring-0'}
                    style={{ resize: 'none' }}
                    value={field.description}
                    onChange={(e: any) => updateDescription(field.index, slide!.index, e.target.value)}
                />
                {hints && <PlainLanguageHints id={hintsId} value={field.description} formId={hints.formId} formLanguage={hints.formLanguage} />}
            </>
        );
    }
    return null;
}

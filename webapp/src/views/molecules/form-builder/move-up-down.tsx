import Divider from '@Components/common/divider';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { ChevronDown, ChevronUp } from 'lucide-react';

export default function MoveUpDown({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) {
    const { moveFieldInASlide, formFields } = useFormFieldsAtom();
    // Count fields on the slide this control belongs to. Reading the global
    // `activeSlide` crashed here: a field can be active while no slide is marked
    // active, leaving `activeSlide` undefined.
    const numberOfFieldsInCurrentSlide = formFields?.[slideIndex]?.properties?.fields?.length ?? 0;

    if (numberOfFieldsInCurrentSlide <= 1) {
        return null;
    }

    return (
        <div className="border-black-400 relative flex flex-col rounded border  ">
            {field.index > 0 && (
                <ChevronUp
                    className="hover:bg-black-400 hover:text-white"
                    onClick={() => {
                        moveFieldInASlide(slideIndex, field.index, field.index - 1);
                    }}
                />
            )}
            {field.index > 0 && field.index !== numberOfFieldsInCurrentSlide - 1 && <Divider />}
            {field.index !== numberOfFieldsInCurrentSlide - 1 && (
                <ChevronDown
                    className="hover:bg-black-400 hover:text-white"
                    onClick={() => {
                        moveFieldInASlide(slideIndex, field.index, field.index + 1);
                    }}
                />
            )}
        </div>
    );
}

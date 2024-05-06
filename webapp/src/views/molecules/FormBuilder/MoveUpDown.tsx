import Divider from '@Components/Common/DataDisplay/Divider';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';

export default function MoveUpDown({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) {
    const { moveFieldInASlide, activeSlide } = useFormFieldsAtom();
    const numberOfFieldsInCurrentSlide = activeSlide!.properties!.fields!.length;

    if (numberOfFieldsInCurrentSlide === 1) {
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

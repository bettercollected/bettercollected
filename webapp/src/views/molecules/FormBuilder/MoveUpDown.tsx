import Divider from '@Components/Common/DataDisplay/Divider';
import {ChevronDown, ChevronUp} from 'lucide-react';
import {StandardFormFieldDto} from "@app/models/dtos/form";
import useFormFieldsAtom from "@app/store/jotai/fieldSelector";

export default function MoveUpDown({field, slideIndex}: { field: StandardFormFieldDto, slideIndex: number }) {

    const {moveFieldInASlide} = useFormFieldsAtom();

    return (
        <div className="relative border-black-400 flex flex-col rounded border  ">
            <ChevronUp className="active:bg-black-300" onClick={() => {
                moveFieldInASlide(slideIndex, field.index, field.index - 1)
            }}/>
            <Divider/>
            <ChevronDown className="active:bg-black-300" onClick={() => {
                moveFieldInASlide(slideIndex, field.index, field.index + 1)
            }}/>
        </div>
    );
}
